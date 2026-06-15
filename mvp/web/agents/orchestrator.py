"""
agents/orchestrator.py
----------------------
The InsurVoice multi-agent orchestrator.

Pipeline for each customer turn:

    customer message
        │
        ▼
    [1] RouterAgent          → which specialist? (claims/billing/policy/general/escalation)
        │
        ▼
    [2] Specialist OR         → domain answer with isolated, focused context
        EscalationAgent       → human handoff + briefing
        │
        ▼
    [3] ComplianceGuard       → EU AI Act + GDPR check before anything is spoken
        │
        ▼
    final response (+ trace of which agents ran)

The orchestrator keeps conversation memory and exposes the same .respond()
interface the rest of the app already uses, so app.py / server.py barely change.

The returned dict includes an `agent_trace` so the UI can SHOW the multi-agent
routing happening — a strong visual for a portfolio demo.
"""

import anthropic
from rag import retrieve_context          # pgvector semantic search (falls back to keyword)
from crm import find_customer, format_customer_context, log_call_to_db
from .router import RouterAgent
from .specialists import SPECIALISTS
from .escalation import EscalationAgent
from .compliance_guard import ComplianceGuard


# ── helpers used by Orchestrator ─────────────────────────────────────────────

def _assess_urgency(intent: str, turn_count: int, handoff_summary: str) -> str:
    """Mirror of n8n_integration.assess_urgency — reused here for DB logging."""
    high = ["legal", "lawsuit", "court", "fraud", "emergency", "fire", "flood"]
    medium = ["angry", "frustrated", "rejected", "denied", "cancel"]
    text = f"{intent} {handoff_summary}".lower()
    if any(k in text for k in high):
        return "high"
    if any(k in text for k in medium) or turn_count >= 5:
        return "medium"
    return "low"


def _call_summary(history: list, intent: str, resolved: bool) -> str:
    """One-line summary for call_log.summary column."""
    topic_map = {
        "escalate_human": "escalation to human agent",
        "file_claim": "filing a claim",
        "claim_status": "claim status check",
        "billing_query": "billing query",
        "policy_renewal": "policy renewal",
        "cancel_policy": "policy cancellation",
        "policy_coverage": "policy coverage question",
    }
    topic = topic_map.get(intent, intent.replace("_", " "))
    status = "resolved" if resolved else "unresolved — follow-up required"
    turns = len([h for h in history if h["role"] == "user"])
    return f"Customer asked about {topic}. {turns} turn(s). {status}."



class Orchestrator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        # Instantiate the agent team once, reuse across turns
        self.router = RouterAgent(self.client)
        self.specialists = {name: cls(self.client) for name, cls in SPECIALISTS.items()}
        self.escalation = EscalationAgent(self.client)
        self.guard = ComplianceGuard(self.client)

        self.history: list[dict] = []
        self.turn_count = 0
        self.consecutive_unresolved = 0
        self.is_first_turn = True
        self.customer: dict | None = None    # cached CRM record for this session

    # ---- context helpers -------------------------------------------------

    def _history_text(self) -> str:
        if not self.history:
            return ""
        return "\n".join(
            f"{'Customer' if t['role']=='user' else 'InsurVoice'}: {t['text']}"
            for t in self.history[-6:]
        )

    def _history_section(self) -> str:
        ht = self._history_text()
        return f"CONVERSATION SO FAR:\n{ht}" if ht else ""

    def _build_context(self, user_message: str, language: str = "en") -> dict:
        lang_names = {
            "en": "English", "de": "German", "es": "Spanish",
            "fr": "French", "it": "Italian", "nl": "Dutch",
            "pt": "Portuguese", "pl": "Polish",
        }
        lang_name = lang_names.get(language, "English")

        # RAG: semantic search over policy_chunks (pgvector), falls back to keyword
        rag_context = retrieve_context(user_message)

        # CRM: look up customer by name/policy number mentioned in message
        if not self.customer:
            self.customer = find_customer(user_message)
        crm_context = format_customer_context(self.customer) if self.customer else ""

        # Combine: CRM record first so agents can personalise, then policy docs
        kb_context = "\n\n".join(filter(None, [crm_context, rag_context]))

        return {
            "kb_context": kb_context,
            "history_text": self._history_text(),
            "history_section": self._history_section() if not self.is_first_turn else "",
            "is_first_turn": self.is_first_turn,
            "language": language,
            "language_name": lang_name,
            "language_instruction": f"IMPORTANT: The customer is speaking {lang_name}. You MUST reply in {lang_name} only.",
        }

    # ---- main turn -------------------------------------------------------

    def respond(self, user_message: str, language: str = "en") -> dict:
        self.turn_count += 1
        trace = []

        ctx = self._build_context(user_message, language)

        # [1] ROUTE
        routing = self.router.call(user_message, ctx)
        route = routing.get("route", "general")
        trace.append({
            "agent": "Router",
            "action": f"→ {route}",
            "detail": routing.get("reasoning", ""),
            "confidence": routing.get("confidence", 0),
        })

        # Decide escalation up front if router says so, or after repeated failures
        escalate = (route == "escalation")

        # [2] HANDLE
        if escalate:
            ctx["escalation_reason"] = routing.get("reasoning", "customer needs human help")
            result = self.escalation.call(user_message, ctx)
            candidate = result.get("response", "")
            handoff = result.get("handoff_summary")
            intent = "escalate_human"
            resolved = False
            trace.append({
                "agent": "EscalationAgent",
                "action": "→ human handoff",
                "detail": "generated caller line + agent briefing",
                "confidence": 1.0,
            })
        else:
            specialist = self.specialists.get(route, self.specialists["general"])
            result = specialist.call(user_message, ctx)
            candidate = result.get("response", "")
            handoff = None
            intent = result.get("intent", routing.get("intent", "general_info"))
            resolved = result.get("resolved", True)
            trace.append({
                "agent": f"{specialist.role}",
                "action": f"answered ({intent})",
                "detail": f"resolved={resolved}",
                "confidence": result.get("confidence", 0),
            })

            # Specialist may itself request escalation
            if result.get("suggested_escalation"):
                ctx["escalation_reason"] = f"{specialist.name} agent could not fully resolve"
                esc = self.escalation.call(user_message, ctx)
                candidate = esc.get("response", candidate)
                handoff = esc.get("handoff_summary")
                escalate = True
                intent = "escalate_human"
                resolved = False
                trace.append({
                    "agent": "EscalationAgent",
                    "action": "→ human handoff",
                    "detail": "specialist requested escalation",
                    "confidence": 1.0,
                })

        # Track repeated non-resolution → safety-net auto-escalation
        if not resolved and not escalate:
            self.consecutive_unresolved += 1
            if self.consecutive_unresolved >= 4:  # only after 4 unresolved turns
                ctx["escalation_reason"] = "two consecutive turns without resolution"
                esc = self.escalation.call(user_message, ctx)
                candidate = esc.get("response", candidate)
                handoff = esc.get("handoff_summary")
                escalate = True
                intent = "escalate_human"
                trace.append({
                    "agent": "EscalationAgent",
                    "action": "→ auto-escalation",
                    "detail": "2 unresolved turns",
                    "confidence": 1.0,
                })
        else:
            self.consecutive_unresolved = 0

        # [3] COMPLIANCE GUARD — always runs, before anything is spoken
        guard_result = self.guard.review(candidate, ctx)
        final_response = guard_result["final_response"]
        trace.append({
            "agent": "ComplianceGuard",
            "action": "✓ passed" if guard_result["compliant"] else "✎ rewrote",
            "detail": ", ".join(guard_result["violations"]) if guard_result["violations"] else "EU AI Act + GDPR OK",
            "confidence": 1.0,
        })

        # Update memory
        self.history.append({"role": "user", "text": user_message})
        self.history.append({"role": "assistant", "text": final_response})
        self.is_first_turn = False

        # Save to Supabase call_log (non-blocking — errors silently skip)
        log_call_to_db({
            "call_id": getattr(self, "call_id", None),
            "customer_id": self.customer.get("id") if self.customer else None,
            "language": ctx.get("language", "en"),
            "intent": intent,
            "route": route,
            "escalated": escalate,
            "resolved": resolved,
            "turn_count": self.turn_count,
            "duration_seconds": 0,         # server.py fills this at end of call
            "compliance_passed": guard_result["compliant"],
            "urgency": _assess_urgency(intent, self.turn_count, handoff or ""),
            "summary": _call_summary(self.history, intent, resolved),
            "handoff_summary": handoff,
        })

        return {
            "response": final_response,
            "intent": intent,
            "route": route,
            "should_escalate": escalate,
            "escalation_reason": ctx.get("escalation_reason") if escalate else None,
            "handoff_summary": handoff,
            "resolved": resolved,
            "compliance": {
                "compliant": guard_result["compliant"],
                "violations": guard_result["violations"],
                "used_llm_review": guard_result["used_llm"],
            },
            "agent_trace": trace,
        }

    def reset(self):
        self.history = []
        self.turn_count = 0
        self.consecutive_unresolved = 0
        self.is_first_turn = True
        self.customer = None
        self.call_id = None
