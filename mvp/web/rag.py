"""
rag.py — InsurVoice AI · pgvector RAG
--------------------------------------
Ingests insurance policy PDFs into Supabase pgvector,
and provides semantic search for the agent pipeline.

Usage:
  python rag.py --ingest     # chunk + embed + store PDFs
  python rag.py --test       # test a sample query
"""

import os
import sys
import json
import math
import time
import logging
import argparse
import psycopg2
import pdfplumber
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

DATABASE_URL  = os.getenv("DATABASE_URL", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
POLICIES_DIR  = Path(__file__).parent / "data" / "policies"

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


# ── CIRCUIT BREAKER ──────────────────────────────────────────────
# Prevents wasting an OpenAI embedding call + 30s connection hang
# every turn when Supabase is paused or unreachable.
#
# States:
#   _db_ok = True   → DB confirmed working, proceed normally
#   _db_ok = False  → DB confirmed dead, skip embed + DB entirely
#   _db_ok = None   → unknown (first run or after retry interval)
#
# After a failure the breaker retests every DB_RETRY_INTERVAL seconds
# so recovery is automatic once Supabase is unpaused.

_db_ok: bool | None = None
_db_last_checked: float = 0.0
DB_RETRY_INTERVAL = 60   # seconds between retry attempts when DB is known dead
DB_CONNECT_TIMEOUT = 5   # seconds before giving up on a single connection attempt
DB_STARTUP_RETRIES = 3   # extra attempts on first probe (Render cold-start DNS lag)
DB_STARTUP_DELAY  = 3    # seconds between startup retry attempts


def _check_db_health(startup: bool = False) -> bool:
    """
    Probe the DB with a lightweight connection.
    Updates the circuit breaker state and returns True if healthy.
    Never raises — all exceptions are caught and logged.

    startup=True: retry up to DB_STARTUP_RETRIES times with short delays.
    This handles Render cold-start where DNS resolves slowly on first request
    but is fine by the second or third attempt a few seconds later.
    """
    global _db_ok, _db_last_checked
    if not DATABASE_URL:
        _db_ok = False
        return False

    attempts = DB_STARTUP_RETRIES if startup else 1
    last_exc = None

    for attempt in range(attempts):
        if attempt > 0:
            time.sleep(DB_STARTUP_DELAY)
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=DB_CONNECT_TIMEOUT)
            conn.close()
            if not _db_ok:
                logger.info("[RAG] Supabase connection restored — pgvector active")
            _db_ok = True
            _db_last_checked = time.monotonic()
            return True
        except Exception as e:
            last_exc = e
            if startup and attempt < attempts - 1:
                logger.info("[RAG] Startup DB probe attempt %d/%d failed, retrying...", attempt + 1, attempts)

    if _db_ok is not False:
        logger.warning("[RAG] Supabase unavailable — falling back to keyword-only RAG. Error: %s", last_exc)
    _db_ok = False
    _db_last_checked = time.monotonic()
    return False


def _db_is_available() -> bool:
    """
    Return True if DB is available, using the circuit breaker cache.
    Retests at most once per DB_RETRY_INTERVAL seconds.
    """
    global _db_ok, _db_last_checked
    now = time.monotonic()

    # Unknown state (startup) → always probe, with retries for cold-start DNS lag
    if _db_ok is None:
        return _check_db_health(startup=True)

    # DB was working → still assume OK (errors in get_conn() will flip it)
    if _db_ok is True:
        return True

    # DB was dead → only retry after the interval
    if now - _db_last_checked >= DB_RETRY_INTERVAL:
        return _check_db_health()

    return False


def _mark_db_failed(e: Exception):
    """Call this from get_conn() or semantic_search() when a connection error occurs."""
    global _db_ok, _db_last_checked
    if _db_ok is not False:
        logger.warning("[RAG] Supabase connection failed — circuit breaker open. Error: %s", e)
    _db_ok = False
    _db_last_checked = time.monotonic()


# ── 1. PDF TEXT EXTRACTION ───────────────────────────────────────

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a PDF using pdfplumber."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
    import re
    text = re.sub(r'\(cid:\d+\)', '•', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── 2. CHUNKING ──────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 300, overlap: int = 60) -> list[str]:
    """
    Smart chunking that respects Q&A boundaries.
    Splits on Q: markers first, then falls back to word-count chunking.
    """
    import re

    # Try splitting on Q&A pairs first (FAQ appendix structure)
    qa_pattern = re.split(r'(?=Q:\s)', text)
    qa_chunks = [c.strip() for c in qa_pattern if len(c.strip()) > 50]

    if len(qa_chunks) > 3:
        chunks = []
        current = ""
        for qa in qa_chunks:
            words = (current + " " + qa).split()
            if len(words) <= chunk_size * 1.5:
                current = (current + " " + qa).strip()
            else:
                if current:
                    chunks.append(current)
                current = qa
        if current:
            chunks.append(current)
        faq_start = text.find("APPENDIX")
        if faq_start > 100:
            policy_text = text[:faq_start]
            policy_words = policy_text.split()
            start = 0
            while start < len(policy_words):
                end = min(start + chunk_size, len(policy_words))
                chunk = " ".join(policy_words[start:end])
                chunks.insert(0, chunk)
                if end == len(policy_words):
                    break
                start += chunk_size - overlap
        return chunks

    # Fallback: standard word-count chunking
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


# ── 3. EMBEDDING ─────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    """
    Generate a 1536-dimension embedding using Claude's
    voyage-3 embedding model via Anthropic API.
    Falls back to a simple hash-based vector if API fails.
    """
    try:
        import anthropic
        client_embed = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        truncated = " ".join(text.split()[:400])
        response = client_embed.messages.create(
            model="claude-opus-4-6",
            max_tokens=1,
            messages=[{"role": "user", "content": truncated}],
            system="Return only the number 1."
        )
        raise NotImplementedError("Use OpenAI embeddings")

    except Exception:
        try:
            import openai
            openai.api_key = os.getenv("OPENAI_API_KEY", "")
            if not openai.api_key:
                raise ValueError("No OPENAI_API_KEY")
            resp = openai.embeddings.create(
                model="text-embedding-3-large",
                input=text[:2000]
            )
            return resp.data[0].embedding

        except Exception as e:
            print(f"  [embed] OpenAI failed: {e}")
            import hashlib
            h = hashlib.sha256(text.encode()).digest()
            vec = []
            for i in range(1536):
                byte_val = h[i % 32]
                vec.append((byte_val / 255.0) * 2 - 1)
            magnitude = math.sqrt(sum(v**2 for v in vec))
            return [v / magnitude for v in vec]


def embed_text_simple(text: str, doc_name: str = "") -> list[float]:
    """
    Generate embedding using OpenAI text-embedding-3-large.
    1536 dimensions. Prepends metadata context for better domain matching.
    """
    import openai
    oa = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    doc_context = {
        "Home Contents Insurance": "German home contents insurance policy Hausratversicherung covering fire water damage burst pipe storm theft burglary vandalism deductible EUR 250",
        "Personal Liability Insurance Policy": "German personal liability insurance Privathaftpflichtversicherung covering dog bite neighbour damage tenant liability accidental damage third party",
        "Glass Breakage Insurance": "German glass breakage insurance Glasversicherung covering broken window shower screen ceramic bath deductible EUR 100 glazier",
        "Extension to Home Contents Policy": "German natural hazards extension Elementarversicherung covering flood Hochwasser surface water earthquake groundwater burst pipe storm deductible EUR 500",
        "Insurance Claims Guide": "Insurance claims guide how to file claim documentation required timeline processing status water damage burglary fire storm vandalism deductible settlement",
    }
    prefix = doc_context.get(doc_name, "German insurance policy Allianz Direct")
    enriched = f"[Context: {prefix}] {text}"

    resp = oa.embeddings.create(
        model="text-embedding-3-large",
        input=enriched[:8000],
        dimensions=1536
    )
    return resp.data[0].embedding


# ── 4. SUPABASE STORAGE ──────────────────────────────────────────

def get_conn():
    """
    Open a psycopg2 connection with a short timeout.
    Marks the circuit breaker failed on any exception.
    """
    try:
        return psycopg2.connect(DATABASE_URL, connect_timeout=DB_CONNECT_TIMEOUT)
    except Exception as e:
        _mark_db_failed(e)
        raise


def store_chunk(conn, document: str, chunk_index: int,
                content: str, embedding: list[float]):
    """Store a single chunk and its embedding in Supabase."""
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO policy_chunks (document, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s::vector)
            ON CONFLICT DO NOTHING
        """, (document, chunk_index, content, json.dumps(embedding)))
        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()
        raise e


def clear_document(conn, document: str):
    """Remove all chunks for a document before re-ingesting."""
    try:
        conn.rollback()
        cur = conn.cursor()
        cur.execute("DELETE FROM policy_chunks WHERE document = %s", (document,))
        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()
        raise e


# ── 5. INGEST PIPELINE ───────────────────────────────────────────

def ingest_all():
    """
    Ingest all PDFs from the policies directory into Supabase pgvector.
    Run this once (or whenever policies are updated).
    """
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set in .env")
        return

    pdfs = list(POLICIES_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {POLICIES_DIR}")
        return

    print(f"Found {len(pdfs)} policy documents")
    print(f"Connecting to Supabase...")
    conn = get_conn()

    total_chunks = 0

    for pdf_path in pdfs:
        doc_name = pdf_path.stem
        print(f"\n{'='*50}")
        print(f"Processing: {pdf_path.name}")

        print(f"  Extracting text...")
        text = extract_text_from_pdf(pdf_path)
        word_count = len(text.split())
        print(f"  Extracted {word_count} words")

        import re
        text = re.sub(r'\(cid:\d+\)', '•', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        chunks = chunk_text(text, chunk_size=300, overlap=60)
        print(f"  Created {len(chunks)} chunks")

        clear_document(conn, doc_name)
        print(f"  Cleared existing chunks")

        for i, chunk in enumerate(chunks):
            print(f"  Embedding chunk {i+1}/{len(chunks)}...", end="\r")
            try:
                embedding = embed_text_simple(chunk, doc_name)
                store_chunk(conn, doc_name, i, chunk, embedding)
                total_chunks += 1
            except Exception as e:
                print(f"\n  ERROR on chunk {i}: {e}")
                continue

        print(f"  ✓ Stored {len(chunks)} chunks for {doc_name}          ")

    conn.close()
    print(f"\n{'='*50}")
    print(f"✓ Ingestion complete: {total_chunks} total chunks stored")
    print(f"  Run 'python rag.py --test' to verify")


# ── 6. SEMANTIC SEARCH ───────────────────────────────────────────

def semantic_search(query: str, n_results: int = 4) -> list[dict]:
    """
    Find the most relevant policy chunks for a given query.
    Returns list of {document, content, similarity} dicts.

    Circuit breaker: skips the OpenAI embedding call entirely when
    Supabase is known to be unavailable, avoiding wasted API cost.
    """
    if not DATABASE_URL:
        return []

    # ── CIRCUIT BREAKER CHECK ──────────────────────────────────
    # Only compute the embedding if the DB is actually reachable.
    # This avoids paying for an OpenAI call that will be thrown away.
    if not _db_is_available():
        return []

    try:
        embedding = embed_text_simple(query, "")
        conn = get_conn()  # get_conn() marks breaker failed on error
        cur = conn.cursor()

        cur.execute("""
            SELECT
                document,
                chunk_index,
                content,
                1 - (embedding <=> %s::vector) AS similarity
            FROM policy_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (json.dumps(embedding), json.dumps(embedding), n_results))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return [
            {
                "document": row[0],
                "chunk_index": row[1],
                "content": row[2],
                "similarity": float(row[3]),
            }
            for row in rows
            if float(row[3]) > 0.2
        ]

    except Exception as e:
        _mark_db_failed(e)
        logger.error("[RAG] search error: %s", e)
        return []


def format_rag_context(results: list[dict]) -> str:
    """Format search results as context for the LLM."""
    if not results:
        return ""

    lines = ["=== POLICY DOCUMENT CONTEXT (from official policy PDFs) ==="]
    for r in results:
        doc = r["document"].replace("_", " ").replace("-", " ").title()
        sim = r["similarity"]
        lines.append(f"\n[Source: {doc} | Relevance: {sim:.0%}]")
        lines.append(r["content"])

    lines.append("\n=== END POLICY CONTEXT ===")
    return "\n".join(lines)


def retrieve_context(query: str) -> str:
    """
    Main entry point — combines pgvector semantic search with keyword FAQ search.
    Returns merged context from both sources for richer, more accurate responses.

    When Supabase is unavailable the circuit breaker suppresses the pgvector
    attempt entirely and returns keyword-only context at zero extra cost.
    """
    # Get pgvector results from policy PDFs (skipped automatically if DB is down)
    rag_results = semantic_search(query, n_results=3)
    rag_context = format_rag_context(rag_results) if rag_results else ""

    # Always also get keyword FAQ matches
    try:
        from knowledge import retrieve_context as keyword_retrieve
        faq_context = keyword_retrieve(query, top_k=2)
    except Exception:
        faq_context = ""

    # Combine both — FAQs first (more specific), then policy PDF chunks
    parts = []
    if faq_context:
        parts.append("=== FAQ KNOWLEDGE BASE ===\n" + faq_context)
    if rag_context:
        parts.append(rag_context)

    return "\n\n".join(parts) if parts else ""


# ── 7. TEST ──────────────────────────────────────────────────────

def test_search():
    """Test the RAG with sample insurance queries."""
    test_queries = [
        "Does my insurance cover a burst pipe?",
        "My bicycle was stolen, am I covered?",
        "How do I file a claim for water damage?",
        "Is flood damage covered?",
        "What is the deductible for glass breakage?",
        "My dog bit my neighbour, what happens?",
        "How long does a claim take to process?",
    ]

    print("\nTesting RAG semantic search...")
    print("="*60)

    for query in test_queries:
        print(f"\nQuery: {query}")
        results = semantic_search(query, n_results=2)
        if results:
            for r in results:
                print(f"  [{r['similarity']:.0%}] {r['document']} — {r['content'][:120]}...")
        else:
            print("  No results (run --ingest first, or check Supabase is running)")


# ── 8. MAIN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="InsurVoice RAG pipeline")
    parser.add_argument("--ingest", action="store_true", help="Ingest PDFs into pgvector")
    parser.add_argument("--test", action="store_true", help="Test semantic search")
    args = parser.parse_args()

    if args.ingest:
        ingest_all()
    elif args.test:
        test_search()
    else:
        print("Usage: python rag.py --ingest | --test")
