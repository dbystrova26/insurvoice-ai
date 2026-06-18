"""
knowledge.py — InsurVoice AI knowledge base retrieval.
Keyword search over insurance FAQs. Used as always-on layer alongside pgvector RAG.
"""

import re
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
        "answer": "File a claim online at mypolicy.allianz-direct.de, by phone, or email schaden@allianz-direct.de. You need your policy number, incident date, description, and photos if available. Claims are acknowledged within 2 business days.",
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
        "id": "billing_monthly",
        "question": "Can I pay monthly instead of annually?",
        "answer": "Yes. Monthly payment is available with a small surcharge of approximately 3 to 5% annually. Annual payment is cheaper overall. You can switch between payment frequencies at your next renewal date.",
        "category": "billing",
    },
    {
        "id": "billing_missed",
        "question": "I missed a payment. What happens?",
        "answer": "If a payment fails, we retry within 5 days. Your policy then enters a grace period of 14 days during which cover remains active. After the grace period, cover may be suspended. Contact us immediately to arrange payment.",
        "category": "billing",
    },
    {
        "id": "billing_portal",
        "question": "How can I change my payment method?",
        "answer": "You can update your payment method in your online customer portal under Account Settings, or call us. We accept direct debit (SEPA), credit card, and annual bank transfer. Changes take effect from the next billing cycle.",
        "category": "billing",
    },
    {
        "id": "premium_increase",
        "question": "Why has my premium increased?",
        "answer": "Premiums change due to annual market adjustments, changes to your risk profile, or a claim in the previous year. Your renewal letter includes a full breakdown. If you believe it is an error, I can escalate to a billing specialist.",
        "category": "billing",
    },
    {
        "id": "general_hours",
        "question": "What are your opening hours?",
        "answer": "Our customer service team is available Monday to Friday 8am to 8pm and Saturday 9am to 5pm. Our claims emergency line is available 24 hours a day, 7 days a week.",
        "category": "general",
    },
    {
        "id": "cancel_policy",
        "question": "How do I cancel my policy?",
        "answer": "Cancel at annual renewal with 4 weeks written notice, or immediately if your circumstances change significantly. Send a signed letter or email to kuendigung@allianz-direct.de with your policy number.",
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
            if faqs and isinstance(faqs[0], dict):
                return faqs
        except Exception:
            pass
    return FAQ_FALLBACK


def retrieve_context(query: str, top_k: int = 2) -> str:
    """
    Keyword search over the knowledge base.
    Strips punctuation before matching so "monthly?" matches "monthly".
    Returns top_k matching FAQs as a context string for the LLM.
    """
    faqs = _load_kb()

    # Strip punctuation from query before splitting into words.
    # FIX [8]: use >= 3 instead of > 3 so short but meaningful insurance
    # terms are included: "pay", "owe", "due", "fee", "tax", "gas", "ice".
    query_clean = re.sub(r"[^\w\s]", " ", query.lower())
    query_words = [w for w in query_clean.split() if len(w) >= 3]

    scored = []
    for faq in faqs:
        if not isinstance(faq, dict):
            continue
        faq_text = (faq.get("question", "") + " " + faq.get("answer", "")).lower()
        score = sum(1 for word in query_words if word in faq_text)
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
