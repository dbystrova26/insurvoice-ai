"""
agents/escalation.py
--------------------
The Escalation subagent. When a call must go to a human, this agent:
  1. Produces the spoken message that hands the caller over
  2. Generates a concise briefing for the human colleague (without leaking
     personal identifiers into logs)

Kept separate from the specialists because handoff quality is its own skill —
a good summary is what makes the human handover feel seamless.
"""

from .base import BaseAgent


class EscalationAgent(BaseAgent):
    name = "escalation"
    role = "Human handoff coordinator"
    max_tokens = 250

    def system_prompt(self, context: dict) -> str:
        return """You coordinate handing an insurance call from the AI to a human colleague.
Produce a warm, brief spoken line for the caller AND a factual one-to-two sentence briefing
for the human agent. Do NOT include policy numbers, full names, or other personal identifiers
in the briefing — summarise the issue, not the identity.

Respond ONLY with a JSON object (no markdown):
{
  "response": "<short spoken handoff line to the caller>",
  "handoff_summary": "<1-2 sentence briefing for the human agent, no personal identifiers>",
  "intent": "escalate_human",
  "resolved": false,
  "escalated": true
}"""

    def call(self, user_message: str, context: dict) -> dict:
        history = context.get("history_text", "")
        reason = context.get("escalation_reason", "customer needs human assistance")
        prompt = (f"Conversation so far:\n{history}\n\n"
                  f"Latest message: {user_message}\n"
                  f"Reason for escalation: {reason}\n\n"
                  f"Generate the handoff.")
        raw = self._call_llm(self.system_prompt(context), prompt)
        return self.parse_json(raw, fallback={
            "response": "I'm connecting you to a colleague who can help with this. One moment please.",
            "handoff_summary": f"Customer query requiring human help. Reason: {reason}.",
            "intent": "escalate_human", "resolved": False, "escalated": True,
        })
