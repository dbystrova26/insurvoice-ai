"""
n8n_integration.py — InsurVoice AI · n8n webhook trigger
"""
import os
import uuid
import datetime
import requests
import threading
import logging  # ADD THIS

log = logging.getLogger(__name__)  # ADD THIS

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")

# ... existing code ...

def fire_n8n_webhook(...) -> bool:
    if not N8N_WEBHOOK_URL:
        log.warning("[n8n] N8N_WEBHOOK_URL not configured")  # CHANGE THIS
        return False
    
    # ... payload creation ...
    
    def _send():
        try:
            log.info(f"[n8n] Sending webhook to: {N8N_WEBHOOK_URL[:50]}...")  # ADD THIS
            r = requests.post(
                N8N_WEBHOOK_URL,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            if r.status_code not in (200, 201):
                log.error(f"[n8n] Webhook returned {r.status_code}: {r.text[:80]}")  # CHANGE THIS
            else:
                log.info(f"[n8n] Webhook sent successfully. Call ID: {payload['call_id']}")  # ADD THIS
        except Exception as e:
            log.error(f"[n8n] Webhook error: {e}")  # CHANGE THIS
    
    threading.Thread(target=_send, daemon=True).start()
    return True
