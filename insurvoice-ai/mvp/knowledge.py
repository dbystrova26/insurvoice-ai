"""
knowledge.py
------------
Knowledge base for InsurBot AI.
Builds a FAISS vector store from insurance FAQs for semantic retrieval.

In production: replace with Pinecone/Weaviate and a document ingestion pipeline.
In MVP: FAISS in-memory, rebuilt on startup from knowledge_base.json.
"""

import json
import pathlib
from typing import Optional

# Lazy imports — only load heavy ML libs when needed
_vectorstore = None


FAQ_FALLBACK = [
    {
        "id": "home_water_damage",
        "question": "Does my home insurance cover water damage from a burst pipe?",
        "answer": "Yes. Burst pipe water damage is covered under your Hausratversicherung as 'Leitungswasser' damage. Covers furniture, electronics, personal belongings. Your EUR 250 deductible applies. Flooding from outside requires separate flood cover.",
        "category": "home_insurance",
        "intents": ["policy_coverage"],
    },
    {
        "id": "claim_process",
        "question": "How do I file a claim?",
        "answer": "File a claim online at mypolicy.example.com, by phone (this line), or email claims@example-insurance.de. You need your policy number, incident date, description, and photos if available. Claims are acknowledged within 2 business days.",
        "category": "claims",
        "intents": ["file_claim"],
    },
    {
        "id": "claim_timeline",
        "question": "How long does claim processing take?",
        "answer": "Standard claims: 10–15 business days after receiving all documents. Complex claims (over EUR 5,000): up to 30 days. Email status updates are sent. Urgent emergency repair claims can be fast-tracked — please say if this is urgent.",
        "category": "claims",
        "intents": ["claim_status"],
    },
    {
        "id": "policy_renewal",
        "question": "How do I renew my policy?",
        "answer": "Policies renew automatically each year. You receive a renewal notice 6 weeks before the renewal date. To cancel, send written notice at least 4 weeks before renewal. To update coverage, call us or use the online portal.",
        "category": "policy",
        "intents": ["policy_renewal"],
    },
    {
        "id": "premium_increase",
        "question": "Why has my premium increased?",
        "answer": "Premiums change due to annual market adjustments, changes to your risk profile, or a claim in the previous year. Your renewal letter includes a full breakdown. If you believe it is an error, I can escalate to a billing specialist.",
        "category": "billing",
        "intents": ["billing_query"],
    },
    {
        "id": "cancel_policy",
        "question": "How do I cancel my policy?",
        "answer": "Cancel at annual renewal with 4 weeks written notice, or immediately if your risk circumstances change significantly. Send a signed letter or email to cancellations@example-insurance.de with your policy number and requested cancellation date.",
        "category": "policy",
        "intents": ["cancel_policy"],
    },
    {
        "id": "escalate",
        "question": "I want to speak to a human agent.",
        "answer": "Of course — I'll connect you to the next available agent right now. Average wait time is 2–3 minutes. I'll prepare a summary so they're ready for you.",
        "category": "escalation",
        "intents": ["escalate_human"],
    },
]


def _load_kb_from_file() -> list[dict]:
    """Load knowledge base from JSON file if available, else use fallback."""
    kb_path = pathlib.Path(__file__).parent / "data" / "knowledge_base.json"
    if kb_path.exists():
        try:
            with open(kb_path, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("faqs", FAQ_FALLBACK)
        except Exception:
            pass
    return FAQ_FALLBACK


def get_kb_as_text() -> str:
    """Returns knowledge base as a plain text string for injection into prompts."""
    faqs = _load_kb_from_file()
    lines = []
    for faq in faqs:
        lines.append(f"Q: {faq['question']}")
        lines.append(f"A: {faq['answer']}")
        lines.append("")
    return "\n".join(lines)


def simple_keyword_search(query: str, top_k: int = 2) -> str:
    """
    Simple keyword-based retrieval fallback (no ML dependencies needed).
    Returns the top_k most relevant FAQ answers as context string.
    """
    faqs = _load_kb_from_file()
    query_lower = query.lower()

    scored = []
    for faq in faqs:
        score = 0
        combined = (faq["question"] + " " + faq["answer"]).lower()
        for word in query_lower.split():
            if len(word) > 3 and word in combined:
                score += 1
        scored.append((score, faq))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [f for _, f in scored[:top_k] if _ > 0]

    if not top:
        top = scored[:1]

    result = []
    for faq in top:
        result.append(f"Q: {faq['question']}\nA: {faq['answer']}")
    return "\n\n".join(result)


def retrieve_context(query: str) -> str:
    """
    Main retrieval function. Uses keyword search (always available).
    In production: swap for vector similarity search.
    """
    return simple_keyword_search(query, top_k=2)
