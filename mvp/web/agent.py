"""
agent.py
--------
InsurVoice AI agent — intent classification, response generation,
escalation logic, conversation memory.

Channel-agnostic: works with text, transcribed voice, or uploaded audio.
Responses are kept short and natural because they will be spoken aloud (TTS).
"""

import json
import re
import logging
import anthropic
from rag import retrieve_context

log = logging.getLogger(__name__)


SYSTEM_PROMPT_TEMPLATE = """You are InsurVoice, an AI voice agent for Allianz Direct insurance. The customer is speaking to you on a voice call — your response will be read aloud by a text-to-speech engine.

VOICE STYLE RULES (critical):
- Keep responses SHORT — 2 to 4 sentences maximum. This is a phone call, not an email.
- Use natural spoken language. No bullet points, no lists, no URLs read aloud, no markdown.
- Spell out anything that must be heard clearly (say "two hundred fifty euros" not "EUR 250" only if needed, otherwise keep it natural).
- Sound warm and human, but never pretend to be human.

EU AI Act compliance:
- On the FIRST turn only: open with "Hello, you're speaking with InsurVoice, an AI assistant for Allianz Direct."
- If asked whether you're a real person: always confirm you are an AI.

Your role:
- Answer insurance questions using ONLY the knowledge base context below.
- If the answer isn't in the knowledge base: say you don't have that detail and offer to connect them to a colleague.
- Never invent policy terms, amounts, claim decisions, or deadlines.

Escalate (should_escalate=true) when:
- Customer asks for a human / agent / "real person"
- Customer is angry, distressed, or threatening
- It's a complaint, legal matter, or needs account-specific data you don't have
- Two turns in a row failed to help

KNOWLEDGE BASE CONTEXT:
{kb_context}

{history_section}

Respond ONLY with a valid JSON object (no markdown, no code fences):
{{
  "intent": "<policy_coverage|file_claim|claim_status|billing_query|policy_renewal|cancel_policy|escalate_human|general_info|out_of_scope>",
  "confidence": <float 0.0-1.0>,
  "response": "<short spoken response>",
  "should_escalate": <true|false>,
  "escalation_reason": "<null or short reason>"
}}"""


ESCALATION_SUMMARY_PROMPT = """A customer was speaking with an AI voice agent and is being transferred to a human colleague.
Write a 2-sentence handoff summary for the human agent:
1. The customer's main issue
2. Key details mentioned (do NOT include policy numbers or personal identifiers)

Conversation:
{history}

Last message: {last_message}
Detected intent: {intent}"""


class InsurVoiceAgent:
    """
    Multi-turn conversation agent for insurance support.

    Maintains conversation history, tracks escalation decisions,
    and generates handoff summaries for human agents.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model  # stored on session so webhook and call_log can read it
        self.conversation_history: list[dict] = []
        self.turn_count: int = 0
        self.consecutive_failures: int = 0
        self.is_first_turn: bool = True
        self._is_greeting_turn: bool = False

    def _build_history_section(self) -> str:
        """Build conversation history for context window."""
        if not self.conversation_history:
            return ""
        lines = ["CONVERSATION SO FAR:"]
        for turn in self.conversation_history[-6:]:
            role = "Customer" if turn["role"] == "user" else "InsurVoice"
            lines.append(f"{role}: {turn['text']}")
        return "\n".join(lines)

    def _parse_response(self, raw: str) -> dict:
        """Parse Claude's JSON response, with fallback handling."""
        raw = raw.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"```$", "", raw).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            return {
                "intent": "general_info",
                "confidence": 0.3,
                "response": "Sorry, I didn't quite catch that. Could you say it again? Or just say 'agent' to reach a colleague.",
                "should_escalate": False,
                "escalation_reason": None,
                "route": "general",
            }

    def respond(self, user_message: str, language: str = "en",
                _is_greeting: bool = False) -> dict:
        """
        Process a user message and return response dict.

        Args:
            user_message: Transcribed or typed text from user
            language: ISO language code (en, de, es, etc.)
            _is_greeting: True for the synthetic server greeting — skips
                          failure tracking so it cannot poison the counter.

        Returns:
            {
                "response": str,
                "intent": str,
                "route": str,
                "should_escalate": bool,
                "escalation_reason": str|None,
                "handoff_summary": str|None,
            }
        """
        self.turn_count += 1

        # Retrieve context from knowledge base
        kb_context = retrieve_context(user_message)

        # Build history section (skip on first turn to allow AI disclosure)
        history_section = self._build_history_section() if not self.is_first_turn else ""

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            kb_context=kb_context,
            history_section=history_section,
        )
        if self.is_first_turn:
            system_prompt += "\n\nThis is turn 1 — you MUST open with the AI disclosure."

        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            result = self._parse_response(msg.content[0].text)
        except anthropic.AuthenticationError:
            raise
        except Exception as e:
            import traceback, logging as _logging
            _logging.getLogger(__name__).error(
                "[agent] respond() exception on turn %d: %s\n%s",
                self.turn_count, e, traceback.format_exc())
            result = {
                "intent": "general_info",
                "confidence": 0.0,
                "response": "I'm having a technical problem. Let me connect you to a colleague right away." if not _is_greeting else "Hello, you're speaking with InsurVoice, an AI assistant for Allianz Direct. How can I help you today?",
                "should_escalate": False if _is_greeting else True,
                "escalation_reason": None if _is_greeting else f"Technical error: {str(e)[:50]}",
                "route": "general" if _is_greeting else "error",
            }

        # Determine route based on intent
        intent = result.get("intent", "general_info")
        if intent in {"file_claim", "claim_status"}:
            route = "claims"
        elif intent in {"policy_coverage", "policy_renewal", "cancel_policy"}:
            route = "policy"
        elif intent == "billing_query":
            route = "billing"
        elif intent in {"escalate_human", "out_of_scope"}:
            route = "escalation"
        else:
            route = "general"

        result["route"] = route

        # FIX [2]: Skip failure tracking entirely for synthetic greeting turns.
        # The greeting is an internal prompt, not a real customer interaction.
        # If the greeting response has low confidence it should NOT count toward
        # the auto-escalation threshold.
        if not _is_greeting:
            if result.get("confidence", 0) < 0.5:
                self.consecutive_failures += 1
            else:
                self.consecutive_failures = 0

            # Auto-escalate after 2 consecutive low-confidence turns
            if self.consecutive_failures >= 2 and not result.get("should_escalate"):
                result["should_escalate"] = True
                result["escalation_reason"] = "Auto-escalation: two unresolved turns"
                result["response"] = "Let me get you to a specialist who can help with this properly."
                # FIX [1]: set intent and route correctly on auto-escalation so the
                # n8n webhook payload accurately reflects an escalation event, not
                # the underlying topic (e.g. billing_query + escalated=True is misleading).
                result["intent"] = "escalate_human"
                result["route"] = "escalation"

        # FIX [3]: Generate handoff summary even on first-turn escalations.
        # Previously this was skipped when conversation_history was empty (history
        # is appended below). Now we build a minimal summary from the user message
        # alone when history is empty.
        handoff_summary = None
        if result.get("should_escalate"):
            if self.conversation_history:
                handoff_summary = self._generate_handoff_summary(user_message, intent)
            else:
                # First-turn escalation — no history yet, summarise from message alone
                handoff_summary = self._generate_handoff_summary(
                    user_message, intent, first_turn=True
                )

        result["handoff_summary"] = handoff_summary

        # Update conversation history (after escalation check — intentional)
        self.conversation_history.append({"role": "user", "text": user_message})
        self.conversation_history.append({"role": "assistant", "text": result["response"]})
        self.is_first_turn = False

        return result

    def _generate_handoff_summary(self, last_message: str, intent: str,
                                   first_turn: bool = False) -> str:
        """Generate brief handoff summary for human agent."""
        if first_turn or not self.conversation_history:
            # FIX [3]: minimal summary when there is no history yet
            prompt_content = (
                f"A customer contacted an insurance AI agent and immediately requested escalation.\n"
                f"Their first message: \"{last_message}\"\n"
                f"Detected intent: {intent}\n\n"
                f"Write a 1-sentence handoff summary for the human agent."
            )
        else:
            history_text = "\n".join(
                f"{'Customer' if t['role'] == 'user' else 'InsurVoice'}: {t['text']}"
                for t in self.conversation_history[-6:]
            )
            prompt_content = ESCALATION_SUMMARY_PROMPT.format(
                history=history_text,
                last_message=last_message,
                intent=intent,
            )

        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=120,
                messages=[{"role": "user", "content": prompt_content}],
            )
            return msg.content[0].text.strip()
        except Exception:
            return f"Customer query: {last_message[:100]}. Intent: {intent}."

    def reset(self):
        """Clear conversation history and reset state."""
        self.conversation_history = []
        self.turn_count = 0
        self.consecutive_failures = 0
        self.is_first_turn = True
