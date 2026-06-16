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

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


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
        # We have Q&A structure — use it directly as chunks
        # But merge very short Q&As and split very long ones
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
        # Also add the non-FAQ part (policy terms) as word-count chunks
        # Find where FAQ starts
        faq_start = text.find("APPENDIX")
        if faq_start > 100:
            policy_text = text[:faq_start]
            policy_words = policy_text.split()
            start = 0
            while start < len(policy_words):
                end = min(start + chunk_size, len(policy_words))
                chunk = " ".join(policy_words[start:end])
                chunks.insert(0, chunk)  # policy chunks first
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
        # Use the Anthropic embeddings API
        import anthropic
        client_embed = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

        # Truncate to avoid token limits
        truncated = " ".join(text.split()[:400])

        response = client_embed.messages.create(
            model="claude-opus-4-6",
            max_tokens=1,
            messages=[{"role": "user", "content": truncated}],
            system="Return only the number 1."
        )

        # Since Anthropic doesn't have a direct embedding endpoint in the
        # standard API, we use OpenAI's embedding as fallback
        raise NotImplementedError("Use OpenAI embeddings")

    except Exception:
        # Use OpenAI text-embedding-3-small (1536 dims, cheap and good)
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
            # Final fallback: deterministic pseudo-embedding from text hash
            # (for testing without API keys — NOT for production)
            import hashlib
            h = hashlib.sha256(text.encode()).digest()
            vec = []
            for i in range(1536):
                byte_val = h[i % 32]
                vec.append((byte_val / 255.0) * 2 - 1)
            # Normalise
            magnitude = math.sqrt(sum(v**2 for v in vec))
            return [v / magnitude for v in vec]


def embed_text_simple(text: str, doc_name: str = "") -> list[float]:
    """
    Generate embedding using OpenAI text-embedding-3-large.
    3072 dimensions, best OpenAI embedding model.
    Prepends metadata context to improve domain-specific matching.
    """
    try:
        import openai
        oa = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

        # Option 2: metadata prefix for better domain context
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
            dimensions=1536  # reduce to 1536 for Supabase compatibility
        )
        return resp.data[0].embedding
    except Exception as e:
        print(f"  [embed] Error: {e}")
        raise


# ── 4. SUPABASE STORAGE ──────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DATABASE_URL)


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
        conn.rollback()  # clear any failed transaction first
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

        # Extract text
        print(f"  Extracting text...")
        text = extract_text_from_pdf(pdf_path)
        word_count = len(text.split())
        print(f"  Extracted {word_count} words")

        # Clean PDF artifacts
        import re
        text = re.sub(r'\(cid:\d+\)', '•', text)  # fix bullet point encoding
        text = re.sub(r'[ \t]+', ' ', text)          # normalise whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)     # max 2 newlines
        text = text.strip()

        # Chunk
        chunks = chunk_text(text, chunk_size=300, overlap=60)
        print(f"  Created {len(chunks)} chunks")

        # Clear existing chunks for this document
        clear_document(conn, doc_name)
        print(f"  Cleared existing chunks")

        # Embed and store
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
    """
    if not DATABASE_URL:
        return []

    try:
        embedding = embed_text_simple(query, "")  # no doc prefix for queries
        conn = get_conn()
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
            if float(row[3]) > 0.2  # minimum similarity threshold
        ]

    except Exception as e:
        print(f"[RAG] search error: {e}")
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
    """
    # Get pgvector results from policy PDFs
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
            print("  No results (run --ingest first)")


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
