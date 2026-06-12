"""
agents/compliance_guard.py
--------------------------
The Compliance Guard subagent — a guardrail layer that inspects every
candidate response BEFORE it is spoken to the customer.

This is the runtime enforcement of the project's EU AI Act + GDPR position.
It mirrors the awesome-codex-subagents "policy-guardrail-designer" and
"responsible-ai-reviewer" philosophy, implemented as a live product layer.

It uses fast deterministic checks first (cheap, no LLM call) and only
invokes the LLM reviewer when a deterministic flag fires — keeping latency
and cost low on the happy path.
"""

import re
from .base import BaseAgent


# Deterministic red-flag patterns — caught without an LLM call
_FORBIDDEN_PATTERNS = [
    # Claiming to be human (EU AI Act Art. 52 violation)
    (r"\b(i am|i'm) (a )?(human|real (person|human)|not (a )?(bot|robot|machine|ai))\b", "ai_identity_violation"),
    # Making a binding decision the system must NOT make
    (r"\b(your claim is (approved|rejected|denied))\b", "unauthorized_decision"),
    (r"\b(i (approve|reject|deny) your)\b", "unauthorized_decision"),
    (r"\byou are (now )?(covered|not covered) for\b.*\b(guarantee|definitely|certainly)\b", "coverage_guarantee"),
    # Financial/medical advice beyond scope
    (r"\b(you should (invest|buy|sell)|i recommend you (invest|purchase))\b", "out_of_scope_advice"),
]

# Personal-data leakage patterns (GDPR) — these should never be READ ALOUD
_PII_PATTERNS = [
    (r"\b[A-Z]{2,4}[-\s]?\d{4,}\b", "policy_number_readout"),    # policy-number-like tokens (e.g. POL123456, AB-12345)
    (r"\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b", "card_number_readout"),  # card-like
]


class ComplianceGuard(BaseAgent):
    name = "compliance_guard"
    role = "EU AI Act + GDPR response guardrail"
    max_tokens = 250

    def quick_check(self, response_text: str, is_first_turn: bool) -> dict:
        """Deterministic checks — no LLM call. Returns flags found."""
        flags = []
        lowered = response_text.lower()

        for pattern, label in _FORBIDDEN_PATTERNS:
            if re.search(pattern, lowered):
                flags.append(label)

        for pattern, label in _PII_PATTERNS:
            if re.search(pattern, response_text):
                flags.append(label)

        return {"flags": flags, "passed": len(flags) == 0}

    def system_prompt(self, context: dict) -> str:
        return """You are the Compliance Guard for InsurVoice, an insurance voice AI operating under the EU AI Act (Limited Risk, Art. 52) and GDPR.

You review a candidate response that is about to be spoken to a customer. Check it against these rules:
1. AI identity (Art. 52): must never claim to be human or deny being an AI.
2. No binding decisions: must NOT approve/reject claims, guarantee coverage, or make underwriting decisions. It may explain general policy, not decide.
3. No personal data read-aloud: must not recite policy numbers, card numbers, or other identifiers.
4. Scope: no financial/investment/legal advice.
5. Accuracy: must not state specific amounts or terms as fact unless they appear in the provided knowledge base.

If the response is compliant, return it unchanged. If it violates a rule, REWRITE it minimally to be compliant while preserving helpfulness.

Respond ONLY with a JSON object (no markdown):
{
  "compliant": <true|false>,
  "violations": ["<rule names violated, empty if none>"],
  "final_response": "<the compliant response — original if already fine, rewritten if not>"
}"""

    def review(self, response_text: str, context: dict) -> dict:
        """
        Full review. Fast deterministic pass first; LLM reviewer only if a flag
        fires (saves latency/cost on the overwhelmingly common clean case).
        Returns: {final_response, compliant, violations, used_llm}
        """
        is_first_turn = context.get("is_first_turn", False)
        quick = self.quick_check(response_text, is_first_turn)

        if quick["passed"]:
            return {
                "final_response": response_text,
                "compliant": True,
                "violations": [],
                "used_llm": False,
            }

        # A deterministic flag fired — escalate to the LLM reviewer to rewrite safely
        prompt = (f"Candidate response to review:\n\"{response_text}\"\n\n"
                  f"Deterministic flags raised: {quick['flags']}\n"
                  f"Knowledge base context:\n{context.get('kb_context', '(none)')}")
        raw = self._call_llm(self.system_prompt(context), prompt)
        result = self.parse_json(raw, fallback={
            "compliant": False,
            "violations": quick["flags"],
            "final_response": "Let me connect you to a colleague who can help with that properly. One moment.",
        })
        result["used_llm"] = True
        return result
