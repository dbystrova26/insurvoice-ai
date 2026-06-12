# Multi-Agent Architecture — InsurVoice AI

**File:** `mvp/agents/ARCHITECTURE.md`

InsurVoice is not a single AI agent. It is a **team of specialized subagents**
coordinated by an orchestrator, with a compliance guard checking every response
before it reaches the customer. This mirrors how production conversational-AI
platforms (e.g. Parloa) structure their systems — and the subagent philosophy
from the `awesome-codex-subagents` library (specialized agents, isolated
contexts, explicit delegation).

## Why multi-agent instead of one big prompt?

A single prompt trying to handle claims, billing, policy, escalation, *and*
compliance becomes long, conflicted, and hard to maintain. Splitting into
focused agents gives:

- **Sharper answers** — each specialist has only the instructions and knowledge
  relevant to its domain, so it performs better on that domain.
- **Isolated context** — the billing agent isn't distracted by claims rules.
- **Independent evolution** — you can improve the claims agent without touching billing.
- **A dedicated safety layer** — compliance is enforced by its own agent, not
  buried in a mega-prompt where it's easy to override.

## The pipeline

```
                         customer message
                                │
                                ▼
                      ┌───────────────────┐
                      │   RouterAgent     │   triage only — picks the specialist
                      │   (orchestrator)  │   route ∈ {claims, billing, policy,
                      └─────────┬─────────┘            escalation, general}
                                │
              ┌─────────────────┼───────────────────┐
              ▼                 ▼                   ▼
     ┌──────────────┐  ┌──────────────┐    ┌──────────────────┐
     │ ClaimsAgent  │  │ BillingAgent │    │  EscalationAgent │
     │ PolicyAgent  │  │ GeneralAgent │    │  (human handoff) │
     └──────┬───────┘  └──────┬───────┘    └────────┬─────────┘
            └─────────────────┴──────────────────────┘
                                │  candidate response
                                ▼
                      ┌───────────────────┐
                      │  ComplianceGuard  │  EU AI Act + GDPR check
                      │  (guardrail)      │  passes ✓ or rewrites ✎
                      └─────────┬─────────┘
                                │
                                ▼
                   final response (spoken via TTS)
```

## The agents

| Agent | File | Responsibility | Sandbox |
|---|---|---|---|
| **RouterAgent** | `router.py` | Classify the message; decide which specialist handles it. Does **not** answer. | read-only triage |
| **ClaimsAgent** | `specialists.py` | Claims: filing, status, documents, timelines. | domain answer |
| **BillingAgent** | `specialists.py` | Premiums, invoices, payments, price changes. | domain answer |
| **PolicyAgent** | `specialists.py` | Coverage, limits, renewals, cancellations. | domain answer |
| **GeneralAgent** | `specialists.py` | Greetings, hours, general info. | domain answer |
| **EscalationAgent** | `escalation.py` | Human handoff line + agent briefing (no PII in logs). | handoff |
| **ComplianceGuard** | `compliance_guard.py` | Reviews every reply: AI-identity (Art. 52), no binding decisions, no PII read-aloud, scope, accuracy. | guardrail |
| **Orchestrator** | `orchestrator.py` | Runs the pipeline, keeps memory, returns the trace. | coordinator |

## The Compliance Guard — the standout feature

Every candidate response passes through `ComplianceGuard.review()` before it is
spoken. It runs in two stages for speed:

1. **Deterministic checks (no LLM call):** fast regex/rule checks for the common,
   unambiguous violations — claiming to be human, approving/rejecting a claim,
   reading out a policy or card number, giving investment advice. On the clean
   happy path (the vast majority of turns) this is the *only* check, so it adds
   near-zero latency or cost.
2. **LLM reviewer (only if a flag fires):** when a deterministic check trips, the
   guard asks the LLM to rewrite the response minimally to be compliant.

This is the **runtime enforcement** of the project's EU AI Act (Limited Risk,
Art. 52) and GDPR position — not just a claim in a document, but a working layer.

## The agent trace

Every `respond()` call returns an `agent_trace` array recording which agents ran,
what they decided, and the compliance outcome. The web interface renders this as
a visible "Multi-agent pipeline" panel, so a demo viewer can *see* the routing
and the compliance check happen — not just the final answer.

Example trace for "Does my home insurance cover a burst pipe?":

```
Router                        → policy        (coverage question about water damage)
Policy and coverage specialist  answered (policy_coverage)   resolved=true
ComplianceGuard                 ✓ passed       EU AI Act + GDPR OK
```

## Extending the system

Adding a new specialist is intentionally simple:

1. Add a class in `specialists.py` subclassing `BaseAgent` with its own
   `system_prompt()`.
2. Register it in the `SPECIALISTS` dict.
3. Add its route to `ROUTES` in `router.py` so the orchestrator can delegate to it.

No other code changes needed — the orchestrator and guard handle it automatically.

## Mapping to the build process

This architecture was itself designed and reviewed using subagents from the
`awesome-codex-subagents` library during development — for example the
`responsible-ai-reviewer` and `policy-guardrail-designer` patterns informed the
ComplianceGuard, and `agent-organizer` / `multi-agent-coordinator` informed the
orchestrator design. The runtime team mirrors that build-time philosophy.
