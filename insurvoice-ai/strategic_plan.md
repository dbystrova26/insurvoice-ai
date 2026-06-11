# Strategic Deployment & Commercialisation Plan — InsurVoice AI

**File:** `strategic_plan.md`  
**Author:** Daria Bystrova | Ironhack AI Consulting Bootcamp | June 2025

---

## 1. Deployment Phases & Timeline

### Overview

| Phase | Name | Duration | Start | End | Goal |
|---|---|---|---|---|---|
| 0 | POC | 3 weeks | Month 1 | Month 1 | Validate core AI capability |
| 1 | Pilot | 8 weeks | Month 2 | Month 3 | Live testing with real customers, limited scope |
| 2 | Full deployment | 3 months | Month 4 | Month 6 | All Tier-1 contacts eligible for AI handling |
| 3 | Scale / expansion | Ongoing | Month 7+ | — | New channels, languages, commercial licensing |

---

### Phase 1: POC (Current state — Month 1)

**Objective:** Prove the technical pipeline works end-to-end. Not a customer-facing deployment.

**Milestones:**
- [ ] Voiceflow dialogue flow built and tested internally
- [ ] n8n workflow operational; Claude API responding correctly
- [ ] Knowledge base covers all 8 intent categories
- [ ] 50 test cases executed; 92%+ accuracy achieved
- [ ] Demo recording produced (2–4 min screen recording)
- [ ] All documentation complete

**KPIs:**
- Intent classification accuracy ≥ 92% on test set
- Escalation logic triggers correctly on all 10 escalation test cases
- End-to-end response time < 3 seconds (n8n + Claude API)

---

### Phase 2: Pilot (Month 2–3)

**Objective:** Deploy to a limited live customer segment. Validate deflection rate and CSAT in production conditions.

**Scope:** Chat channel only (not phone). Customers who contact via chat widget on the website are offered the AI agent first. 30% of chat volume — approximately 180 contacts/day.

**Milestones:**
- Week 1–2: Deploy to 30% of chat contacts; human agents monitor all conversations
- Week 3–4: Run blind QA review of 100 AI-handled conversations
- Week 5–6: Review deflection rate and CSAT data; adjust KB and prompts
- Week 7–8: Decide: expand or pause. Decision gate: deflection ≥ 50%, CSAT ≥ 3.8/5

**KPIs:**
- AI deflection rate ≥ 50% (Tier-1 contacts resolved without human)
- CSAT for AI-handled contacts ≥ 3.8/5
- Zero BaFin-reportable incidents
- Escalation quality score ≥ 4/5 (human agents rate handoff summaries)

---

### Phase 3: Full Deployment (Month 4–6)

**Objective:** Route all eligible Tier-1 contacts to AI. Integrate with CRM for policy lookup.

**Milestones:**
- Month 4: Expand to 100% of chat volume; add Salesforce read-only CRM integration (policy status lookup)
- Month 5: Deploy German-language version; extend KB to German content
- Month 5: Add voice channel (Voiceflow voice + Deepgram STT)
- Month 6: Full monitoring dashboard live; monthly compliance review procedure formalised

**KPIs:**
- AI deflection rate ≥ 60% across all channels
- Average wait time < 30 seconds for AI-handled contacts
- CSAT ≥ 4.0/5
- Cost per AI-handled contact < EUR 0.05

---

### Phase 4: Scale / Expansion (Month 7+)

**Objective:** Commercialise the platform — offer as SaaS to other insurance companies in DACH.

**Milestones:**
- Month 7: Package product for external licensing; set up multi-tenant architecture
- Month 8: IHIF / InsurTech Germany conference — launch announcement
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
- **Insurance association partnerships:** GDV (German Insurance Association) — co-marketing access to member firms
- **Anthropic partner network:** Listed as Anthropic solution partner — inbound leads from their enterprise sales team

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
| **Parloa** | EUR 100k+ enterprise contracts; requires dedicated implementation team; 6-month deployment | EUR 399 to start; POC deployable in days; no professional services lock-in |
| **Cognigy** | Similar enterprise pricing; complex; German-market focus | Simpler setup; insurance-native KB; modern LLM (Claude) not rule-based |
| **Generic chatbots (Intercom, Freshdesk AI)** | Not insurance-specific; weak intent classification for complex queries | Domain-specific KB; RAG architecture; insurance-trained prompts |
| **Build in-house** | 12–18 month development; EUR 200k+ cost | Working in weeks; fraction of the cost |

---

## 3. Stakeholder Communication Plan

| Stakeholder | Key message | Channel | Timing | Delivered by |
|---|---|---|---|---|
| **CEO / COO** | EUR 1.2M annual value; 9-day payback; competitive positioning vs Parloa | Executive briefing + 1-page business case | Before pilot approval | AI Consultant / Project Lead |
| **Head of Customer Service** | Agents focus on complex cases; AI handles the queue; you own the escalation policy | Workshop + live demo | Week 1 of pilot | Project Lead + CX Lead |
| **Contact Centre Agents** | Your jobs are not at risk; Tier-1 offloaded = more interesting work + less queue stress | Team meeting + FAQ document | Before pilot launch | Head of Customer Service |
| **Legal & Compliance** | Limited risk (EU AI Act); GDPR DPIA complete; BaFin IDD scope excluded; Anthropic DPA | Compliance documentation package | Pre-pilot; updated each phase | Project Lead + External Counsel |
| **IT / Engineering** | Voiceflow + n8n + Railway; no on-prem; API keys via environment variables; architecture docs provided | Technical briefing + architecture diagram | Pre-pilot | Developer |
| **Customers** | "I'm InsurVoice, an AI assistant" — disclosed at every first interaction | In-product (automatic) | Live from day 1 | System (automated) |

---

## 4. Key Performance Indicators by Phase

| KPI | Phase 1 (POC) | Phase 2 (Pilot) | Phase 3 (Full) | Phase 4 (Scale) |
|---|---|---|---|---|
| AI deflection rate | N/A (internal test) | ≥ 50% | ≥ 60% | ≥ 70% |
| CSAT (AI contacts) | N/A | ≥ 3.8/5 | ≥ 4.0/5 | ≥ 4.2/5 |
| Response accuracy (QA) | ≥ 92% | ≥ 92% | ≥ 94% | ≥ 95% |
| Avg response time | < 3 sec | < 2 sec | < 1.5 sec | < 1 sec |
| Cost per AI contact | EUR 0.017 | EUR 0.017 | EUR 0.015 | EUR 0.012 |
| External clients (MRR) | 0 | 0 | 0 | 5 clients / EUR 8k MRR |
| GDPR incidents | 0 | 0 | 0 | 0 |

---

## 5. Commercialisation Model

**Model: B2B SaaS with professional services**

InsurVoice AI is commercialised as a vertical SaaS product for the insurance industry. Allianz Direct operates as the first client and reference case — credible because the product was built to solve their own problem.

**Why SaaS (not consulting service or internal tool):**
- The core IP (insurance knowledge base, prompt architecture, escalation logic) is reusable across clients
- Marginal cost of each additional client is near zero (shared infrastructure)
- Recurring revenue (monthly subscription) creates predictable cashflow
- Insurance is a vertical with hundreds of potential clients in DACH alone
- SaaS multiples (8–15× ARR) are higher than consulting firm multiples (1–2× revenue)

**Revenue model:**
- Subscription (80% of revenue): Monthly SaaS fees — predictable, low churn
- Setup / implementation fees (15%): One-time per client — funds the implementation cost
- Custom development (5%): Bespoke integrations for enterprise clients

**18-month revenue target:**
- Month 9: 3 clients × avg EUR 900/month = EUR 2,700 MRR
- Month 12: 5 clients × avg EUR 1,100/month = EUR 5,500 MRR
- Month 18: 10 clients × avg EUR 1,400/month = EUR 14,000 MRR + 1 enterprise @ EUR 3,500 = EUR 17,500 MRR (EUR 210k ARR)
