"""
agents/router.py
----------------
The Router (orchestrator) subagent.

Its ONLY job is triage: read the customer's message and decide which
specialist agent should handle it. It does not answer the question itself.

This is the "explicit delegation" pattern — a coordinator that routes work
to the right specialist, exactly as described in the awesome-codex-subagents
orchestration philosophy.
"""

from .base import BaseAgent


ROUTES = {
    "claims": "Claims questions: filing a claim, claim status, claim disputes, what to do after an incident",
    "billing": "Billing questions: premiums, invoices, payment methods, charges, price increases",
    "policy": "Policy questions: what's covered, coverage limits, renewals, cancellations, adding people",
    "escalation": "Anything requiring a human: explicit request for an agent, complaints, anger, legal threats, account-specific data the AI cannot access",
    "general": "Greetings, opening hours, general info, small talk, or anything that doesn't fit the above",
}


class RouterAgent(BaseAgent):
    name = "router"
    role = "Intent triage and delegation"
    max_tokens = 200  # routing is cheap — small response

    def system_prompt(self, context: dict) -> str:
        routes_desc = "\n".join(f"- {k}: {v}" for k, v in ROUTES.items())
        return f"""You are the Router for InsurVoice, an insurance voice assistant. Your ONLY job is to classify the customer's message and decide which specialist should handle it. You do NOT answer the question.

Available specialists:
{routes_desc}

Analyse the customer's latest message in the context of the conversation, then respond ONLY with a JSON object (no markdown):
{{
  "route": "<claims|billing|policy|escalation|general>",
  "intent": "<specific intent label, e.g. file_claim, premium_increase, policy_coverage>",
  "confidence": <0.0-1.0>,
  "reasoning": "<one short phrase on why this route>"
}}

Routing rules:
- If the customer asks for a human, is angry, threatens legal action, or wants something requiring their specific account data → route "escalation".
- If unsure between two specialists, pick the more specific one.
- Greetings and vague openers → route "general"."""

    def call(self, user_message: str, context: dict) -> dict:
        history = context.get("history_text", "")
        prompt = f"{history}\n\nCustomer's latest message: {user_message}" if history else user_message
        raw = self._call_llm(self.system_prompt(context), prompt)
        return self.parse_json(raw, fallback={
            "route": "general",
            "intent": "unknown",
            "confidence": 0.4,
            "reasoning": "fallback — could not parse router output",
        })
