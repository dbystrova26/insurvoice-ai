"""
knowledge.py — InsurVoice AI knowledge base retrieval.
Keyword search over insurance FAQs. Production: replace with vector DB.
"""

import json
import pathlib

FAQ_FALLBACK = [
    {
        "id": "home_water_damage",
        "question": "Does my home insurance cover water damage from a burst pipe?",
        "answer": "Yes. Burst pipe water damage is covered under your Hausratversicherung as Leitungswasser damage. Covers furniture, electronics, personal belongings. Your EUR 250 deductible applies. Flooding from outside requires separate flood cover.",
        "category": "home_insurance",
    },
    {
        "id": "claim_process",
        "question": "How do I file a claim?",
        "answer": "File a claim online at mypolicy.example.com, by phone, or email claims@example-insurance.de. You need your policy number, incident date, description, and photos if available. Claims are acknowledged within 2 business days.",
        "category": "claims",
    },
    {
        "id": "claim_timeline",
        "question": "How long does claim processing take?",
        "answer": "Standard claims: 10 to 15 business days. Complex claims over EUR 5000: up to 30 days. Email updates are sent throughout. Urgent emergency repair claims can be fast-tracked.",
        "category": "claims",
    },
    {
        "id": "policy_renewal",
        "question": "How do I renew my policy?",
        "answer": "Policies renew automatically each year. You receive a renewal notice 6 weeks before the renewal date. To cancel, send written notice at least 4 weeks before renewal. To update coverage, call us or use the online portal.",
        "category": "policy",
    },
    {
        "id": "premium_increase",
        "question": "Why has my premium increased?",
        "answer": "Premiums change due to annual market adjustments, changes to your risk profile, or a claim in the previous year. Your renewal letter includes a full breakdown. If you believe it is an error, I can escalate to a billing specialist.",
        "category": "billing",
    },
    {
        "id": "cancel_policy",
        "question": "How do I cancel my policy?",
        "answer": "Cancel at annual renewal with 4 weeks written notice, or immediately if your circumstances change significantly. Send a signed letter or email to cancellations@example-insurance.de with your policy number.",
        "category": "policy",
    },
    {
        "id": "escalate",
        "question": "I want to speak to a human agent.",
        "answer": "Of course. I will connect you to the next available agent right now. Average wait time is 2 to 3 minutes.",
        "category": "escalation",
    },
]


def _load_kb() -> list:
    """Load FAQs from file or use hardcoded fallback. Always returns list of dicts."""
    kb_path = pathlib.Path(__file__).parent / "data" / "knowledge_base.json"
    if kb_path.exists():
        try:
            with open(kb_path, encoding="utf-8") as f:
                data = json.load(f)
            faqs = data.get("faqs", [])
            # Ensure every item is a dict — guard against list-of-lists from bad data
            if faqs and isinstance(faqs[0], dict):
                return faqs
        except Exception:
            pass
    return FAQ_FALLBACK


def retrieve_context(query: str, top_k: int = 2) -> str:
    """
    Keyword search over the knowledge base.
    Returns top_k matching FAQs as a context string for the LLM.
    """
    faqs = _load_kb()
    query_lower = query.lower()

    scored = []
    for faq in faqs:
        # Safety: skip anything that is not a dict
        if not isinstance(faq, dict):
            continue
        score = sum(
            1 for word in query_lower.split()
            if len(word) > 3 and word in (faq.get("question", "") + " " + faq.get("answer", "")).lower()
        )
        scored.append((score, faq))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Take top results with score > 0, fallback to top 1 regardless
    top = [faq for score, faq in scored[:top_k] if score > 0]
    if not top:
        top = [scored[0][1]] if scored else []

    return "\n\n".join(
        f"Q: {faq['question']}\nA: {faq['answer']}"
        for faq in top
        if isinstance(faq, dict)
    )


def get_kb_as_text() -> str:
    """Full KB as text — used for prompt injection."""
    return retrieve_context("", top_k=len(_load_kb()))
