"""
crm.py — InsurVoice AI · Supabase CRM lookup
---------------------------------------------
Looks up customer records by name or policy number.
Used by the orchestrator to personalise responses.
"""

import os
import re
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")


def _get_conn():
    """Get a database connection."""
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def find_customer(text: str) -> Optional[dict]:
    """
    Try to find a customer from a message containing their name or policy number.
    Returns customer dict with claims or None if not found.
    """
    if not DATABASE_URL:
        return None

    # Extract policy number if mentioned (e.g. POL-4821)
    policy_match = re.search(r'POL-\d{3,6}', text, re.IGNORECASE)
    policy_number = policy_match.group(0).upper() if policy_match else None

    # Extract potential name — look for capitalised words
    # Simple heuristic: two consecutive capitalised words
    name_match = re.search(r'\b([A-Z][a-zäöüß]+)\s+([A-Z][a-zäöüß]+)\b', text)
    name = f"{name_match.group(1)} {name_match.group(2)}" if name_match else None

    if not policy_number and not name:
        return None

    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Try policy number first (more precise)
        if policy_number:
            cur.execute("""
                SELECT id, name, email, phone, language, policy_number,
                       policy_type, policy_status, premium_monthly, next_payment, address
                FROM customers WHERE UPPER(policy_number) = %s
            """, (policy_number,))
        else:
            # Search by name (case-insensitive partial match)
            cur.execute("""
                SELECT id, name, email, phone, language, policy_number,
                       policy_type, policy_status, premium_monthly, next_payment, address
                FROM customers WHERE LOWER(name) LIKE LOWER(%s)
                LIMIT 1
            """, (f"%{name}%",))

        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return None

        cols = ['id', 'name', 'email', 'phone', 'language', 'policy_number',
                'policy_type', 'policy_status', 'premium_monthly', 'next_payment', 'address']
        customer = dict(zip(cols, row))

        # Get their claims
        cur.execute("""
            SELECT claim_number, type, description, filed_date, status,
                   expected_decision, amount_claimed, amount_settled
            FROM claims WHERE customer_id = %s
            ORDER BY filed_date DESC
        """, (customer['id'],))

        claim_cols = ['claim_number', 'type', 'description', 'filed_date', 'status',
                      'expected_decision', 'amount_claimed', 'amount_settled']
        customer['claims'] = [dict(zip(claim_cols, r)) for r in cur.fetchall()]

        cur.close()
        conn.close()
        return customer

    except Exception as e:
        print(f"[CRM] lookup error: {e}")
        return None


def format_customer_context(customer: dict) -> str:
    """Format customer record as context string for the LLM."""
    if not customer:
        return ""

    lines = [
        "=== CUSTOMER RECORD (from CRM) ===",
        f"Name: {customer['name']}",
        f"Policy: {customer['policy_number']} ({customer['policy_type']})",
        f"Status: {customer['policy_status']}",
        f"Monthly premium: EUR {customer['premium_monthly']}",
        f"Next payment: {customer['next_payment']}",
        f"Address: {customer['address']}",
        f"Email: {customer['email']}",
        f"Preferred language: {customer['language']}",
    ]

    if customer.get('claims'):
        lines.append("\nClaims on file:")
        for c in customer['claims']:
            status_map = {
                'under_assessment': 'Under assessment',
                'approved': 'Approved',
                'settled': 'Settled',
                'rejected': 'Rejected',
            }
            status = status_map.get(c['status'], c['status'])
            line = f"  • {c['claim_number']}: {c['type']} — {status}"
            if c['expected_decision']:
                line += f" (decision by {c['expected_decision']})"
            if c['amount_settled']:
                line += f" — settled EUR {c['amount_settled']}"
            lines.append(line)
    else:
        lines.append("No claims on file.")

    lines.append("=== END CUSTOMER RECORD ===")
    return "\n".join(lines)


def log_call_to_db(call_data: dict):
    """Log a completed call to the call_log table."""
    if not DATABASE_URL:
        return
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO call_log
              (call_id, customer_id, language, intent, route, escalated,
               resolved, turn_count, duration_seconds, compliance_passed,
               urgency, summary, handoff_summary)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (call_id) DO NOTHING
        """, (
            call_data.get('call_id'),
            call_data.get('customer_id'),
            call_data.get('language', 'en'),
            call_data.get('intent'),
            call_data.get('route'),
            call_data.get('escalated', False),
            call_data.get('resolved', False),
            call_data.get('turn_count', 1),
            call_data.get('duration_seconds', 0),
            call_data.get('compliance_passed', True),
            call_data.get('urgency', 'low'),
            call_data.get('summary'),
            call_data.get('handoff_summary'),
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[CRM] log error: {e}")
