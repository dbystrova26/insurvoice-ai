# Use Case Definition — InsurVoice AI Voice Agent

**Project:** InsurVoice AI — Conversational AI Customer Service Agent  
**Author:** Daria Bystrova  
**Bootcamp:** Ironhack AI Consulting Bootcamp  
**Date:** June 2025  
**Industry inspiration:** Parloa (Berlin, ~$1B valuation, Series B 2024) — conversational AI for enterprise customer service

---

## Business Problem Statement

**Who:** Allianz Direct GmbH (fictional client) — a mid-size direct insurance provider operating in Germany and Austria. ~280 employees, ~180,000 policyholders. Direct distribution model with no broker network: all customer interaction goes through a centralised contact centre of 42 agents.

**The problem:** The contact centre handles approximately 1,800 inbound calls and 600 chat sessions per day. Analysis of call recordings shows that **68% of all contacts are Tier-1 queries** — routine questions about policy coverage, claims status, billing, and renewal that require no specialist knowledge and follow predictable scripts. Despite this, every contact routes to a human agent, resulting in:

- Average handling time (AHT) of 6.2 minutes per contact
- Average queue wait of 4.1 minutes during business hours
- Agent occupancy rate of 91% — leaving no capacity for complex or high-value interactions
- Customer satisfaction (CSAT) score of 3.4/5 — driven primarily by wait time complaints
- Annual contact centre cost of EUR 2.1M for 42 agents at EUR 50,000 loaded cost

**The core question every AI consultant must answer:** Can we deflect 60%+ of Tier-1 contacts to an AI agent, reduce wait times to zero, cut costs materially, and improve CSAT — without degrading service quality or creating compliance exposure?

---

## Company Profile

| Field | Detail |
|---|---|
| Company name | Allianz Direct GmbH (fictional) |
| Industry | Direct insurance (home, contents, liability, travel) |
| Size | SME — 280 employees, EUR ~45M annual revenue |
| Geography | Germany and Austria |
| Distribution model | Direct only — no brokers |
| Contact centre | 42 agents, 8am–8pm Mon–Sat |
| Current AI use | None — fully manual call handling |
| CRM | Salesforce (assumed) |
| Key pain point | 68% of calls are Tier-1, answered by expensive human agents |

---

## Proposed AI Solution

**InsurVoice AI** is a conversational AI agent that handles Tier-1 customer service contacts autonomously across chat and (in production) voice channels.

**Type of AI system:** Multi-capability — combines:
- **Intent classification** (what does the customer want?)
- **Retrieval-Augmented Generation / RAG** (finding the right answer from the knowledge base)
- **Generative response** (producing a natural, on-brand reply)
- **Dialogue management** (multi-turn conversation with context memory)
- **Escalation logic** (routing to human when needed)

**What the AI does, step by step:**
1. Customer initiates contact via chat widget or phone (voice via Voiceflow TTS/STR in production)
2. Agent identifies itself as an AI (EU AI Act Article 52 compliance)
3. Customer's message is classified into one of 8 top-level intent categories
4. Agent retrieves relevant policy/FAQ content from the knowledge base (RAG)
5. Claude generates a natural, context-aware response
6. Agent manages multi-turn dialogue — asks clarifying questions, handles follow-ups
7. At any point: customer can request escalation; agent hands off with a context summary
8. Conversation is logged (anonymised) for quality review

**Technology stack (POC):** Voiceflow (dialogue flow) + n8n (orchestration) + Claude API (intent classification + generation) + JSON knowledge base

**Technology stack (MVP/production):** Python + Streamlit + LangChain + Claude API + vector store (FAISS) + Render deployment

---

## Key Stakeholders

| Stakeholder | Role | Primary interest | What they need to hear |
|---|---|---|---|
| CEO / Managing Director | Executive sponsor | Cost reduction + CSAT improvement | ROI, competitive positioning, risk mitigation |
| Head of Customer Service | Product owner | Tool augments team; agents focus on complex cases | Escalation quality, agent workload impact |
| Contact Centre Agents | Affected workforce | Job security; tool doesn't replace them | Tier-1 offloaded = more time for complex/rewarding work |
| Legal & Compliance | Risk governance | GDPR, EU AI Act, BaFin sensitivity | Full compliance documentation; human always available |
| IT / Engineering | Integration owner | CRM integration, uptime, security | Architecture, API specs, SLA |
| Policyholders (customers) | End users | Fast, accurate answers; no endless queues | Transparent AI disclosure; easy human escalation |
| BaFin (regulator) | Indirect stakeholder | No automated insurance decisions | System is information-only; no binding decisions made |

---

## Success Criteria

The following measurable outcomes define project success at 12-month full deployment:

| # | Metric | Baseline | Target | Measurement method |
|---|---|---|---|---|
| 1 | AI deflection rate (Tier-1 contacts resolved without human) | 0% | ≥ 60% | Contact centre analytics |
| 2 | Average wait time for AI-handled contacts | 4.1 min | < 30 seconds | System logs |
| 3 | Customer satisfaction (CSAT) for AI-handled contacts | 3.4/5 | ≥ 4.0/5 | Post-contact survey |
| 4 | AI response accuracy (verified by QA sample review) | N/A | ≥ 92% | Monthly QA audit (10% sample) |
| 5 | Cost per contact (AI-handled) | EUR 4.73 | < EUR 0.50 | Finance reporting |
| 6 | Human agent capacity freed for complex contacts | 0% | ≥ 40% of shift time | Workforce management system |

---

## Out-of-Scope Boundaries

The following are **explicitly excluded** from this solution. These boundaries are not limitations — they are deliberate design decisions to maintain compliance and scope control.

| Out of scope | Reason |
|---|---|
| Making binding insurance decisions (accepting/rejecting claims) | Would trigger EU AI Act high-risk classification (Annex III) and BaFin scrutiny |
| Providing personalised financial or legal advice | Requires FCA/BaFin licence; beyond an information agent's mandate |
| Processing payments | Requires PCI-DSS compliance; separate payment system |
| Accessing or modifying core policy records | CRM integration is Phase 3; POC/MVP uses knowledge base only |
| Voice channel (phone calls) | Phase 2 — POC demonstrates chat only; voice requires additional STT/TTS infrastructure |
| Languages other than German and English | Phase 3 — initial deployment German-first |
| Handling complaints requiring regulatory escalation | Complaints with legal implications always route to senior human agent |

---

## Relationship to Parloa

This project is positioned in the same product category as [Parloa](https://www.parloa.com) — a Berlin-based conversational AI platform that raised a Series B in 2024 at approximately USD 1B valuation. Parloa builds enterprise-grade AI voice and chat agents for insurance, telco, banking, and retail clients. This POC demonstrates the same core capability — autonomous Tier-1 contact handling with seamless human escalation — at a proof-of-concept scale, using open tools (Voiceflow, n8n, Anthropic Claude) rather than Parloa's proprietary platform.

Parloa's existence validates the market: enterprise buyers are actively purchasing this category of product. The addressable market in DACH alone (insurance + telco + banking contact centres) exceeds EUR 800M annually.
