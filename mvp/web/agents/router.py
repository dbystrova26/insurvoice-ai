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
    "claims": "Filing a claim, claim status, claim disputes, required documents for a claim, what to do after an incident",
    "billing": "Premiums, invoices, payment methods, charges, price increases, refunds, discounts",
    "policy": "What is covered, coverage limits, renewals, cancellations, adding people, liability coverage, damage scenarios (dog, accidental breakage), what insurance covers",
    "escalation": "ONLY when customer EXPLICITLY asks to speak to a human agent, expresses serious anger, or makes a legal threat. Do NOT route process complaints, AI identity questions, or document location questions to escalation.",
    "general": "Greetings, opening hours, contact info, portal access, policy documents location, how to make a complaint, whether the agent is AI or human, small talk, anything not fitting above",
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
- Route "escalation" ONLY for: explicit "I want to speak to a human/agent", serious anger/threats, legal threats.
- "Am I speaking to a human/AI?" → route "general" (factual identity question, not an escalation request).
- "How do I complain?" or "How do I make a complaint?" → route "general" (process question, not a complaint itself).
- "Where are my documents?" or "How do I log in?" → route "general".
- Dog damage, accidental breakage, liability questions → route "policy".
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
