"""
InsurVoice multi-agent system.

A Router delegates each customer turn to a specialist agent
(claims / billing / policy / general) or the escalation agent,
and a Compliance Guard reviews every response before it is spoken.

Usage:
    from agents import Orchestrator
    agent = Orchestrator(api_key)
    result = agent.respond("does my policy cover a burst pipe?")
"""

from .orchestrator import Orchestrator
from .router import RouterAgent, ROUTES
from .specialists import SPECIALISTS
from .escalation import EscalationAgent
from .compliance_guard import ComplianceGuard

__all__ = ["Orchestrator", "RouterAgent", "ROUTES", "SPECIALISTS",
           "EscalationAgent", "ComplianceGuard"]
