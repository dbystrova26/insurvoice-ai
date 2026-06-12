"""
agents/base.py
--------------
Base class for all InsurVoice subagents.

Each subagent has:
  - a name and role description
  - its own system prompt (isolated "context" / persona)
  - a single call() method that takes the conversation + user message
    and returns a structured result

This mirrors the subagent philosophy from awesome-codex-subagents:
specialized agents, isolated contexts, explicit delegation by an orchestrator.
"""

import json
import re
import anthropic


class BaseAgent:
    """Foundation for every specialized subagent."""

    name: str = "base"
    role: str = "generic agent"
    model: str = "claude-opus-4-6"
    max_tokens: int = 400

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def system_prompt(self, context: dict) -> str:
        """Override in each subagent. `context` carries KB text, history, flags."""
        raise NotImplementedError

    def _call_llm(self, system: str, user_message: str) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return msg.content[0].text.strip()

    @staticmethod
    def parse_json(raw: str, fallback: dict) -> dict:
        """Robust JSON parse with markdown-fence stripping and fallback."""
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
        return fallback

    def call(self, user_message: str, context: dict) -> dict:
        """Override in each subagent. Returns a structured result dict."""
        raise NotImplementedError
