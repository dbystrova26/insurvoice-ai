# Strategic Deployment & Commercialisation Plan — InsurVoice AI

**File:** `strategic_plan.md`  
**Author:** Daria Bystrova | Ironhack AI Consulting Bootcamp | June 2026

---

## 1. Deployment Phases & Timeline

### Overview

| Phase | Name | Duration | Start | End | Goal |
|---|---|---|---|---|---|
| 0 | POC | 3 weeks | Month 1 | Month 1 | Validate core AI voice loop |
| 1 | Pilot | 8 weeks | Month 2 | Month 3 | Live testing with real customers, limited scope |
| 2 | Full deployment | 3 months | Month 4 | Month 6 | All Tier-1 contacts eligible for AI handling |
| 3 | Scale / expansion | Ongoing | Month 7+ | — | New channels, languages, commercial licensing |

---

### Phase 0: POC (Completed)

**Objective:** Prove the technical pipeline works end-to-end. Not a customer-facing deployment.

**What was built:**
- n8n workflow orchestrating full STT → Claude → TTS loop
- Deepgram nova-3 live WebSocket streaming STT
- 154-FAQ knowledge base with keyword RAG
- 7-agent Python pipeline: Router + Claims + Billing + Policy + General + Escalation + ComplianceGuard
- Simli WebRTC lip-synced avatar (Tina persona)
- Supabase PostgreSQL CRM — 20 mock customers, 10 claims
- n8n automation: Gmail + Google Sheets + Slack after every call
- EU AI Act Art. 52 + GDPR compliance enforced at runtime
- Deployed on Render.com

**KPIs achieved:**
- Routing accuracy: 83% (target ≥85% — router prompt refinement in progress, expected 90%+)
- Keyword coverage: 78% ✅ (target ≥70%)
- Compliance rate: 100% ✅
- Avg response time: 6.3s ✅ (target <8s)

---

### Phase 1: Pilot (Month 2–3)

**Objective:** Deploy to a limited live customer segment. Validate deflection rate and CSAT in production conditions.

**Scope:** Web chat channel. Customers contacting via chat widget offered AI agent first. 30% of chat volume — approximately 180 contacts/day.

**Milestones:**
- Week 1–2: Deploy to 30% of chat contacts; human agents monitor all conversations
- Week 3–4: Blind QA review of 100 AI-handled conversations
- Week 5–6: Review deflection rate and CSAT; adjust KB and prompts
- Week 7–8: Decision gate: deflection ≥50%, CSAT ≥3.8/5 → expand

**KPIs:**
- AI deflection rate ≥50%
- CSAT for AI-handled contacts ≥3.8/5
- Zero BaFin-reportable incidents
- Escalation quality score ≥4/5 (human agents rate handoff summaries)

---

### Phase 2: Full Deployment (Month 4–6)

**Objective:** Route all eligible Tier-1 contacts to AI. Integrate with real CRM for policy lookup.

**Milestones:**
- Month 4: Expand to 100% of chat volume; add real CRM API integration (replace mock Supabase data with live policy system)
- Month 5: Deploy German-language voice channel; add Twilio telephony for phone calls
- Month 5: Replace keyword RAG with pgvector semantic search on Supabase
- Month 6: Live operations dashboard (Looker Studio or Grafana); monthly compliance review formalised

**KPIs:**
- AI deflection rate ≥60% across all channels
- Average wait time <30 seconds
- CSAT ≥4.0/5
- Cost per AI-handled contact <EUR 0.05

---

### Phase 3: Scale / Expansion (Month 7+)

**Objective:** Commercialise the platform — offer as SaaS to other insurance companies in DACH.

**Milestones:**
- Month 7: Multi-tenant architecture; white-label Tina persona
- Month 8: InsurTech Germany / DIA Amsterdam — launch announcement
- Month 9: First paying external client onboarded
- Month 12: 5 paying clients; EUR 8,000 MRR

---

## 2. Go-to-Market Strategy

### Target Buyers

**Primary:** Head of Customer Experience / COO at mid-size direct insurance companies in Germany, Austria, and Switzerland (DACH).

| Segment | Profile | Pain | Willingness to pay |
|---|---|---|---|
| Direct insurers (DACH) | 100–500 employees, direct distribution, high chat/call volume | Contact centre costs, CSAT, 24/7 gap | EUR 800–3,000/month |
| Insurtech platforms | Embedded insurance, API-first, no legacy contact centre | Scale customer support without headcount | EUR 500–1,500/month |
| Insurance brokers (large) | 50+ agents, own customer service function | Same pain as direct insurers | EUR 400–1,200/month |
| White-label (telco/banking) | Non-insurance contact centres with same Tier-1 problem | Replicable use case | Enterprise licence EUR 20k+/year |

### Sales Channel

- **Direct outreach:** LinkedIn to Heads of Customer Experience at top 50 DACH direct insurers
- **InsurTech events:** InsurTech Germany (Frankfurt), DIA Amsterdam, IHIF
- **Insurance association partnerships:** GDV (German Insurance Association)
- **Anthropic partner network:** Listed as Anthropic solution partner — inbound leads from enterprise sales team

### Pricing Model

| Tier | Price | Includes | Target |
|---|---|---|---|
| Starter | EUR 399/month | 3,000 contacts/month; 1 KB; standard support | Small insurers, brokers |
| Business | EUR 1,200/month | 15,000 contacts/month; 3 KBs; CRM integration; priority support | Mid-size direct insurers |
| Enterprise | EUR 3,500+/month | Unlimited; white-label; voice channel; dedicated CSM; SLA | Large insurers, telco |
| Setup fee | EUR 5,000–15,000 | Implementation, KB build, training | All tiers |

### Key Differentiator vs Alternatives

| Alternative | Weakness | InsurVoice advantage |
|---|---|---|
| **Parloa** | EUR 100k+ enterprise contracts; 6-month deployment; requires dedicated implementation team | EUR 399 to start; POC deployable in days; open architecture |
| **Cognigy** | Complex; enterprise pricing; rule-based NLU; slow to update KB | Modern LLM (Claude); insurance-native KB; RAG architecture |
| **Generic chatbots (Intercom, Freshdesk AI)** | Not insurance-specific; weak intent classification | Domain-specific KB; 7-agent pipeline; lip-synced avatar |
| **Build in-house** | 12–18 month development; EUR 200k+ cost | Working in weeks; fraction of the cost |

---

## 3. Stakeholder Communication Plan

| Stakeholder | Key message | Channel | Timing | Delivered by |
|---|---|---|---|---|
| **CEO / COO** | EUR 1.2M annual value; 9-day payback; competitive positioning | Executive briefing + 1-page business case | Before pilot approval | AI Consultant / Project Lead |
| **Head of Customer Service** | Agents focus on complex cases; AI handles the queue | Workshop + live demo | Week 1 of pilot | Project Lead + CX Lead |
| **Contact Centre Agents** | Your jobs are not at risk; Tier-1 offloaded = more interesting work | Team meeting + FAQ | Before pilot launch | Head of Customer Service |
| **Legal & Compliance** | Limited risk (EU AI Act); GDPR DPIA complete; BaFin IDD scope excluded | Compliance documentation package | Pre-pilot | Project Lead + External Counsel |
| **IT / Engineering** | Flask + n8n + Render + Supabase; no on-prem; API keys via environment variables | Technical briefing + architecture diagram | Pre-pilot | Developer |
| **Customers** | "Hi, I'm Tina, an AI assistant" — disclosed at every first interaction | In-product (automatic) | Live from day 1 | System (automated) |

---

## 4. Key Performance Indicators by Phase

| KPI | Phase 0 (POC) | Phase 1 (Pilot) | Phase 2 (Full) | Phase 3 (Scale) |
|---|---|---|---|---|
| AI deflection rate | N/A (internal test) | ≥50% | ≥60% | ≥70% |
| CSAT (AI contacts) | N/A | ≥3.8/5 | ≥4.0/5 | ≥4.2/5 |
| Routing accuracy (QA) | 83% (improving) | ≥90% | ≥92% | ≥95% |
| Avg response time | 6.3s | <4s | <2s | <1.5s |
| Cost per AI contact | EUR 0.017 | EUR 0.017 | EUR 0.015 | EUR 0.012 |
| External clients (MRR) | 0 | 0 | 0 | 5 clients / EUR 8k MRR |
| GDPR incidents | 0 | 0 | 0 | 0 |

---

## 5. Commercialisation Model

**Model: B2B SaaS with professional services**

InsurVoice AI is commercialised as a vertical SaaS product for the insurance industry. Allianz Direct operates as the first client and reference case.

**Why SaaS:**
- Core IP (insurance KB, multi-agent prompt architecture, compliance layer) reusable across clients
- Marginal cost of each additional client near zero (shared infrastructure on Render + Supabase)
- Recurring revenue creates predictable cashflow
- Insurance is a vertical with hundreds of potential clients in DACH alone
- SaaS multiples (8–15× ARR) higher than consulting firm multiples (1–2× revenue)

**Revenue model:**
- Subscription (80%): Monthly SaaS fees
- Setup / implementation (15%): One-time per client
- Custom development (5%): Bespoke integrations for enterprise

**18-month revenue target:**
- Month 9: 3 clients × avg EUR 900/month = EUR 2,700 MRR
- Month 12: 5 clients × avg EUR 1,100/month = EUR 5,500 MRR
- Month 18: 10 clients × avg EUR 1,400/month + 1 enterprise @ EUR 3,500 = EUR 17,500 MRR (EUR 210k ARR)
