"""
agents/specialists.py
---------------------
Specialist subagents. Each handles ONE domain with a focused persona and
only the knowledge relevant to its area. The Router delegates to exactly one.

This is the core subagent benefit: domain-specific intelligence with an
isolated context, rather than one giant prompt trying to do everything.
"""

from .base import BaseAgent


# Shared voice + compliance rules injected into every specialist
VOICE_RULES = """VOICE STYLE (this will be spoken aloud by text-to-speech):
- Keep it SHORT: 2-4 sentences. This is a phone call.
- Natural spoken language. No lists, no markdown, no URLs read aloud.
- Warm and professional. Never pretend to be human.

EU AI Act: if the customer asks whether you are a real person, always confirm you are an AI.
If this is the first turn of the call, briefly note you are InsurVoice, an AI assistant for Allianz Direct.

Ground every answer in the KNOWLEDGE BASE below. If the answer is not there,
say you don't have that detail and offer to connect them to a colleague — do NOT invent
policy terms, amounts, or deadlines."""


def _response_schema() -> str:
    return """Respond ONLY with a JSON object (no markdown):
{
  "response": "<your short spoken answer>",
  "intent": "<specific intent label>",
  "confidence": <0.0-1.0>,
  "resolved": <true if the customer's question is fully answered, false if a follow-up or human is likely needed>,
  "suggested_escalation": <true|false — set true ONLY if you cannot help and a human is needed>
}"""


class ClaimsAgent(BaseAgent):
    name = "claims"
    role = "Insurance claims specialist"

    def system_prompt(self, context: dict) -> str:
        return f"""You are the Claims Specialist at InsurVoice (Allianz Direct). You handle ONLY claims-related queries: filing claims, claim status, required documents, timelines, and what to do after an incident. You are warm, reassuring, and precise — people calling about claims are often stressed.

{VOICE_RULES}

KNOWLEDGE BASE:
{context.get('kb_context', '')}

{context.get('history_section', '')}

{_response_schema()}"""

    def call(self, user_message: str, context: dict) -> dict:
        raw = self._call_llm(self.system_prompt(context), user_message)
        return self.parse_json(raw, fallback={
            "response": "I can help with your claim, but I need to connect you to a claims colleague to be sure. One moment.",
            "intent": "file_claim", "confidence": 0.5, "resolved": False, "suggested_escalation": True,
        })


class BillingAgent(BaseAgent):
    name = "billing"
    role = "Billing and payments specialist"

    def system_prompt(self, context: dict) -> str:
        return f"""You are the Billing Specialist at InsurVoice (Allianz Direct). You handle ONLY billing queries: premiums, invoices, payment methods, charges, and premium changes. You are clear and transparent about money matters, and you never guess at specific amounts on someone's account.

{VOICE_RULES}

Important: you can explain GENERAL billing policy from the knowledge base, but you cannot see the caller's specific account balance or charges. For anything account-specific, offer to escalate.

KNOWLEDGE BASE:
{context.get('kb_context', '')}

{context.get('history_section', '')}

{_response_schema()}"""

    def call(self, user_message: str, context: dict) -> dict:
        raw = self._call_llm(self.system_prompt(context), user_message)
        return self.parse_json(raw, fallback={
            "response": "For your specific billing question I'll connect you to a billing colleague who can see your account. One moment.",
            "intent": "billing_query", "confidence": 0.5, "resolved": False, "suggested_escalation": True,
        })


class PolicyAgent(BaseAgent):
    name = "policy"
    role = "Policy and coverage specialist"

    def system_prompt(self, context: dict) -> str:
        return f"""You are the Policy Specialist at InsurVoice (Allianz Direct). You handle ONLY policy queries: what's covered, coverage limits, deductibles, renewals, cancellations, and adding people to a policy. You explain coverage clearly and set correct expectations about what is and isn't included.

{VOICE_RULES}

KNOWLEDGE BASE:
{context.get('kb_context', '')}

{context.get('history_section', '')}

{_response_schema()}"""

    def call(self, user_message: str, context: dict) -> dict:
        raw = self._call_llm(self.system_prompt(context), user_message)
        return self.parse_json(raw, fallback={
            "response": "Let me connect you to a policy colleague to confirm the exact terms for your situation. One moment.",
            "intent": "policy_coverage", "confidence": 0.5, "resolved": False, "suggested_escalation": True,
        })


class GeneralAgent(BaseAgent):
    name = "general"
    role = "General enquiries and greeting"

    def system_prompt(self, context: dict) -> str:
        return f"""You are the front-desk agent at InsurVoice (Allianz Direct). You handle greetings, general information (opening hours, how things work), and small talk. You're friendly and quickly guide the customer toward how you can help.

{VOICE_RULES}

KNOWLEDGE BASE:
{context.get('kb_context', '')}

{context.get('history_section', '')}

{_response_schema()}"""

    def call(self, user_message: str, context: dict) -> dict:
        raw = self._call_llm(self.system_prompt(context), user_message)
        return self.parse_json(raw, fallback={
            "response": "Hello, you're speaking with InsurVoice, an AI assistant for Allianz Direct. How can I help you today?",
            "intent": "general_info", "confidence": 0.6, "resolved": True, "suggested_escalation": False,
        })


# Registry the orchestrator uses to look up the right specialist
SPECIALISTS = {
    "claims": ClaimsAgent,
    "billing": BillingAgent,
    "policy": PolicyAgent,
    "general": GeneralAgent,
}
