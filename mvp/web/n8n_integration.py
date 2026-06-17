"""
n8n_integration.py — InsurVoice AI · n8n webhook trigger
---------------------------------------------------------
Call this at the end of every conversation turn to send
call data to n8n for Gmail + Google Sheets + Slack automation.
"""
import os
import uuid
import datetime
import requests
import threading
import logging

log = logging.getLogger(__name__)

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")


def assess_urgency(intent: str, turn_count: int, handoff_summary: str) -> str:
    """Classify escalation urgency based on intent and conversation length."""
    high_urgency_keywords = [
        "legal", "lawsuit", "solicitor", "court", "fraud", "complaint",
        "urgent", "emergency", "fire", "flood", "uninhabitable", "police"
    ]
    medium_urgency_keywords = [
        "angry", "frustrated", "rejected", "denied", "overcharge", "cancel"
    ]
    text = f"{intent} {handoff_summary}".lower()
    if any(k in text for k in high_urgency_keywords):
        return "high"
    if any(k in text for k in medium_urgency_keywords) or turn_count >= 5:
        return "medium"
    return "low"


def generate_call_summary(conversation_history: list, intent: str, resolved: bool) -> str:
    """Generate a plain-English summary of the call."""
    if not conversation_history:
        return f"Customer contacted InsurVoice regarding: {intent}. " + \
               ("Issue resolved by AI." if resolved else "Issue referred for follow-up.")
    topic_map = {
        "claims": "filing or checking a claim",
        "billing": "billing or payment queries",
        "policy": "policy coverage or changes",
        "general": "general information",
        "escalation": "a matter requiring human assistance",
    }
    topic = topic_map.get(intent, intent)
    status = "resolved during the call" if resolved else "not fully resolved and requires follow-up"
    turns = len(conversation_history)
    return (f"Customer contacted InsurVoice AI regarding {topic}. "
            f"The conversation lasted {turns} exchange{'s' if turns != 1 else ''}. "
            f"The matter was {status}.")


def fire_n8n_webhook(
    call_id: str,
    intent: str,
    route: str,
    language: str,
    turn_count: int,
    resolved: bool,
    escalated: bool,
    handoff_summary: str,
    compliance_passed: bool,
    conversation_history: list,
    customer_name: str = None,
    customer_email: str = None,
    duration_seconds: int = 0,
) -> bool:
    """
    Fire the n8n webhook in a background thread (non-blocking).
    Returns True if webhook was sent, False if no URL configured.
    """
    if not N8N_WEBHOOK_URL:
        log.warning("[n8n] N8N_WEBHOOK_URL not configured")
        return False
    
    urgency = assess_urgency(intent, turn_count, handoff_summary or "")
    summary = generate_call_summary(conversation_history, intent, resolved)
    
    payload = {
        "call_id": call_id,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "intent": intent,
        "route": route,
        "language": language,
        "turn_count": turn_count,
        "resolved": resolved,
        "escalated": escalated,
        "handoff_summary": handoff_summary or "",
        "compliance_passed": compliance_passed,
        "urgency": urgency,
        "summary": summary,
        "duration_seconds": duration_seconds,
        "customer_name": customer_name or "Unknown",
        "customer_email": customer_email or "",
    }

    def _send():
        try:
            log.info(f"[n8n] Sending escalation webhook to: {N8N_WEBHOOK_URL[:60]}...")
            log.info(f"[n8n] Payload - Call ID: {call_id}, Intent: {intent}, Escalated: {escalated}")
            
            r = requests.post(
                N8N_WEBHOOK_URL,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            
            if r.status_code not in (200, 201):
                log.error(f"[n8n] Webhook returned {r.status_code}: {r.text[:100]}")
            else:
                log.info(f"[n8n] ✅ Webhook sent successfully. Call ID: {call_id}")
        except Exception as e:
            log.error(f"[n8n] ❌ Webhook error: {str(e)}")

    threading.Thread(target=_send, daemon=True).start()
    return True
