"""
agents/orchestrator.py
----------------------
InsurVoice multi-agent orchestrator with:
- Tina greeting on first turn
- Language selection flow
- Supabase CRM lookup by name + policy number
- Full multi-agent pipeline: Router → Specialist → ComplianceGuard
"""

import anthropic
from knowledge import retrieve_context
from .router import RouterAgent
from .specialists import SPECIALISTS
from .escalation import EscalationAgent
from .compliance_guard import ComplianceGuard

# Try to import CRM — graceful fallback if Supabase not configured
try:
    from crm import find_customer, format_customer_context
    CRM_AVAILABLE = True
except ImportError:
    CRM_AVAILABLE = False
    def find_customer(text): return None
    def format_customer_context(c): return ""


LANG_NAMES = {
    "en": "English", "de": "German", "es": "Spanish",
    "fr": "French", "it": "Italian", "nl": "Dutch",
    "pt": "Portuguese", "pl": "Polish",
}

# Conversation states
STATE_GREETING    = "greeting"       # First turn — Tina introduces herself
STATE_LANGUAGE    = "language"       # Waiting for language selection
STATE_IDENTIFY    = "identify"       # Waiting for name + policy number
STATE_ACTIVE      = "active"         # Normal conversation


class Orchestrator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.router = RouterAgent(self.client)
        self.specialists = {name: cls(self.client) for name, cls in SPECIALISTS.items()}
        self.escalation = EscalationAgent(self.client)
        self.guard = ComplianceGuard(self.client)

        self.history: list[dict] = []
        self.turn_count = 0
        self.consecutive_unresolved = 0
        self.state = STATE_GREETING
        self.language = "en"
        self.customer = None          # CRM record once identified
        self.customer_name = None
        self.customer_email = None

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _history_text(self) -> str:
        if not self.history:
            return ""
        return "\n".join(
            f"{'Customer' if t['role']=='user' else 'Tina'}: {t['text']}"
            for t in self.history[-6:]
        )

    def _history_section(self) -> str:
        ht = self._history_text()
        return f"CONVERSATION SO FAR:\n{ht}" if ht else ""

    def _build_context(self, user_message: str) -> dict:
        lang_name = LANG_NAMES.get(self.language, "English")
        lang_instruction = f"IMPORTANT: Reply in {lang_name} only."

        # CRM context
        crm_context = ""
        if self.customer:
            crm_context = format_customer_context(self.customer)
            self.customer_name = self.customer.get("name")
            self.customer_email = self.customer.get("email")

        return {
            "kb_context": retrieve_context(user_message),
            "crm_context": crm_context,
            "history_text": self._history_text(),
            "history_section": self._history_section(),
            "is_first_turn": self.state == STATE_GREETING,
            "language": self.language,
            "language_name": lang_name,
            "language_instruction": lang_instruction,
            "customer": self.customer,
            "customer_name": self.customer_name,
        }

    def _detect_language(self, text: str) -> str:
        """Detect language from user response."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["english", "en", "inglés", "anglais"]):
            return "en"
        if any(w in text_lower for w in ["deutsch", "german", "de", "auf deutsch", "alemán"]):
            return "de"
        if any(w in text_lower for w in ["español", "spanish", "es", "espagnol"]):
            return "es"
        if any(w in text_lower for w in ["français", "french", "fr", "franzosisch"]):
            return "fr"
        if any(w in text_lower for w in ["italiano", "italian", "it"]):
            return "it"
        return self.language  # keep current if unclear

    def _make_response(self, text: str, intent: str = "greeting",
                       route: str = "general", trace: list = None) -> dict:
        """Helper to build a response dict."""
        self.history.append({"role": "assistant", "text": text})
        return {
            "response": text,
            "intent": intent,
            "route": route,
            "should_escalate": False,
            "escalation_reason": None,
            "handoff_summary": None,
            "resolved": True,
            "compliance": {"compliant": True, "violations": [], "used_llm_review": False},
            "agent_trace": trace or [],
        }

    # ── Main turn ─────────────────────────────────────────────────────────────

    def respond(self, user_message: str, language: str = None) -> dict:
        self.turn_count += 1

        # Update language from STT detection if provided and not already set by user
        if language and language != "en" and self.state not in (STATE_LANGUAGE,):
            self.language = language

        # Record user message
        self.history.append({"role": "user", "text": user_message})

        # ── STATE: GREETING (first turn) ──────────────────────────────────────
        if self.state == STATE_GREETING:
            self.state = STATE_LANGUAGE
            greeting = (
                "Hi, I'm Tina, your AI insurance assistant from Allianz Direct. "
                "I'm here to help you with any questions about your policy, claims, billing, or coverage. "
                "Before we start — would you prefer to speak in English or Deutsch?"
            )
            return self._make_response(greeting, "greeting", "general", [{
                "agent": "Tina", "action": "greeting", "detail": "language selection prompt"
            }])

        # ── STATE: LANGUAGE SELECTION ─────────────────────────────────────────
        if self.state == STATE_LANGUAGE:
            detected = self._detect_language(user_message)
            self.language = detected
            self.state = STATE_IDENTIFY
            lang_name = LANG_NAMES.get(detected, "English")

            if detected == "de":
                confirm = (
                    f"Perfekt, ich helfe Ihnen gerne auf Deutsch! "
                    f"Darf ich Ihren Namen und Ihre Versicherungsnummer erfragen, "
                    f"damit ich Ihre Unterlagen aufrufen kann?"
                )
            elif detected == "es":
                confirm = (
                    f"¡Perfecto! Le atenderé en español. "
                    f"¿Podría indicarme su nombre y número de póliza para consultar su expediente?"
                )
            elif detected == "fr":
                confirm = (
                    f"Parfait, je vous aiderai en français ! "
                    f"Pourriez-vous me donner votre nom et numéro de police pour accéder à votre dossier ?"
                )
            else:
                confirm = (
                    f"Perfect, I'll help you in English! "
                    f"Could you please give me your name and policy number "
                    f"so I can pull up your account?"
                )

            return self._make_response(confirm, "language_confirmed", "general", [{
                "agent": "Tina", "action": f"language → {lang_name}", "detail": "requesting identification"
            }])

        # ── STATE: IDENTIFY (waiting for name + policy number) ────────────────
        if self.state == STATE_IDENTIFY:
            # Try CRM lookup
            customer = find_customer(user_message) if CRM_AVAILABLE else None

            if customer:
                self.customer = customer
                self.customer_name = customer["name"]
                self.customer_email = customer.get("email")
                # Switch to customer's preferred language if set
                if customer.get("language") and customer["language"] != "en":
                    self.language = customer["language"]
                self.state = STATE_ACTIVE

                # Build personalised greeting
                name = customer["name"].split()[0]  # first name only
                policy = customer["policy_number"]
                policy_type = customer["policy_type"]
                status = customer["policy_status"]
                premium = customer["premium_monthly"]
                next_pay = customer["next_payment"]

                claims = customer.get("claims", [])
                claim_line = ""
                if claims:
                    latest = claims[0]
                    claim_status_map = {
                        "under_assessment": "currently under assessment",
                        "approved": "has been approved",
                        "settled": "has been settled",
                        "rejected": "was unfortunately rejected",
                    }
                    cs = claim_status_map.get(latest["status"], latest["status"])
                    claim_line = f" Your most recent claim {latest['claim_number']} {cs}."

                if self.language == "de":
                    response = (
                        f"Hallo {name}! Ich habe Ihre Unterlagen gefunden. "
                        f"Ihre {policy_type}-Police {policy} ist {status}. "
                        f"Ihre nächste Zahlung beträgt EUR {premium} am {next_pay}."
                        f"{claim_line} Wie kann ich Ihnen heute helfen?"
                    )
                else:
                    response = (
                        f"Hello {name}! I've found your account. "
                        f"Your {policy_type} policy {policy} is {status}. "
                        f"Your next payment of EUR {premium} is due on {next_pay}."
                        f"{claim_line} How can I help you today?"
                    )

                return self._make_response(response, "crm_lookup_success", "general", [{
                    "agent": "Tina CRM",
                    "action": f"found {customer['policy_number']}",
                    "detail": f"{customer['name']} · {customer['policy_type']}"
                }])

            else:
                # Not found — move to active anyway, proceed without CRM
                self.state = STATE_ACTIVE
                if self.language == "de":
                    response = (
                        "Ich konnte leider keine passende Police finden. "
                        "Kein Problem — ich helfe Ihnen trotzdem gerne weiter. "
                        "Was kann ich für Sie tun?"
                    )
                else:
                    response = (
                        "I wasn't able to find a matching policy with those details. "
                        "No worries — I can still help you with your question. "
                        "What can I assist you with today?"
                    )
                return self._make_response(response, "crm_lookup_failed", "general", [{
                    "agent": "Tina CRM", "action": "not found", "detail": "proceeding without account"
                }])

        # ── STATE: ACTIVE — full multi-agent pipeline ─────────────────────────
        trace = []
        ctx = self._build_context(user_message)

        # [1] ROUTE
        routing = self.router.call(user_message, ctx)
        route = routing.get("route", "general")
        trace.append({
            "agent": "Router",
            "action": f"→ {route}",
            "detail": routing.get("reasoning", ""),
            "confidence": routing.get("confidence", 0),
        })

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

        if not resolved and not escalate:
            self.consecutive_unresolved += 1
            if self.consecutive_unresolved >= 4:
                ctx["escalation_reason"] = "repeated unresolved turns"
                esc = self.escalation.call(user_message, ctx)
                candidate = esc.get("response", candidate)
                handoff = esc.get("handoff_summary")
                escalate = True
                intent = "escalate_human"
                trace.append({
                    "agent": "EscalationAgent",
                    "action": "→ auto-escalation",
                    "detail": f"{self.consecutive_unresolved} unresolved turns",
                    "confidence": 1.0,
                })
        else:
            self.consecutive_unresolved = 0

        # [3] COMPLIANCE GUARD
        guard_result = self.guard.review(candidate, ctx)
        final_response = guard_result["final_response"]
        trace.append({
            "agent": "ComplianceGuard",
            "action": "✓ passed" if guard_result["compliant"] else "✎ rewrote",
            "detail": ", ".join(guard_result["violations"]) if guard_result["violations"] else "EU AI Act + GDPR OK",
            "confidence": 1.0,
        })

        self.history.append({"role": "assistant", "text": final_response})

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
        self.state = STATE_GREETING
        self.language = "en"
        self.customer = None
        self.customer_name = None
        self.customer_email = None
