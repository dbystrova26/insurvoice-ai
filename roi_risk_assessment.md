# ROI & Risk Assessment — InsurVoice AI

**Project:** InsurVoice AI — Conversational AI Customer Service Agent  
**Author:** Daria Bystrova | Ironhack AI Consulting Bootcamp | June 2026

---

## Part 1: ROI Analysis

### 1.1 Upfront Cost Estimate

| Item | Cost (EUR) | Basis |
|---|---|---|
| Solution design & consulting | 12,000 | 160h @ EUR 75/h |
| Flask + SocketIO voice interface build | 3,500 | Custom Python development |
| n8n workflow setup & automation | 800 | Configuration + testing time |
| Multi-agent pipeline (7 agents) | 4,000 | ~50h developer time |
| Knowledge base creation & QA (154 FAQs) | 3,000 | Content review, FAQ writing, 40h |
| Supabase CRM schema + mock data | 500 | Database design + seeding |
| Simli avatar integration | 800 | WebRTC setup + UI build |
| Staff training (agents + QA team, 12 people) | 2,400 | 4h per person @ EUR 50/h loaded |
| Legal / compliance review (GDPR + EU AI Act) | 2,500 | ~12h external counsel |
| Contingency (15%) | 4,350 | Standard project buffer |
| **TOTAL UPFRONT** | **33,850** | |

### 1.2 Ongoing Annual Costs

| Item | Annual (EUR) | Basis |
|---|---|---|
| Anthropic Claude API (claude-opus-4-6) | 4,800 | ~1,000 contacts/day × 365 × EUR 0.013 avg |
| Deepgram nova-3 STT | 600 | 12,000 min/month free tier; ~EUR 50/month overage |
| ElevenLabs TTS | 1,200 | EUR 99/month Creator plan for production volume |
| Render.com hosting | 168 | EUR 14/month Starter plan |
| Supabase PostgreSQL | 0 | Free tier sufficient for current scale |
| n8n Cloud | 240 | EUR 20/month Starter plan |
| Simli WebRTC | 600 | EUR 50/month for production minutes |
| Maintenance & prompt tuning (20h/year) | 1,500 | EUR 75/h |
| QA monitoring (10% sample review) | 2,600 | 0.5h/day agent time |
| **TOTAL ANNUAL** | **11,708** | |

### 1.3 Business Value Estimate

**Baseline (current state):**
- 42 agents × EUR 50,000 loaded cost = EUR 2,100,000/year total contact centre cost
- 2,400 contacts/day × 365 = 876,000 contacts/year
- Cost per contact: EUR 2.40
- Tier-1 contacts (68%): 595,680/year — currently handled by humans at full cost

**After AI deployment (target: 60% deflection of Tier-1 contacts):**
- AI deflects: 595,680 × 60% = **357,408 contacts/year**
- Cost per AI-handled contact: EUR 0.013 (API) + EUR 0.004 (infra) ≈ **EUR 0.017**
- Saving per deflected contact: EUR 2.40 − EUR 0.017 = **EUR 2.383**
- **Annual saving from deflection: 357,408 × EUR 2.383 = EUR 851,694**

**Additional value streams:**
- Reduced overtime / peak staffing: EUR 45,000/year
- CSAT improvement → reduced churn (0.5pp churn reduction × 180,000 policyholders × EUR 380 avg policy): EUR 342,000/year
- 24/7 availability (outside 8am–8pm): EUR 28,000/year

**Total annual value: EUR 1,266,694**

### 1.4 ROI Calculation

| Period | Total Cost | Total Value | Net Benefit | ROI |
|---|---|---|---|---|
| **12 months** | EUR 45,558 (upfront + year 1) | EUR 1,266,694 | EUR 1,221,136 | **2,681%** |
| **36 months** | EUR 57,274 (upfront + 3 years) | EUR 3,800,082 | EUR 3,742,808 | **6,535%** |

### 1.5 Assumptions

| # | Assumption | Value | Justification |
|---|---|---|---|
| A1 | Tier-1 contact rate | 68% | Industry benchmark (Gartner 2023: 65–72% for insurance) |
| A2 | AI deflection rate (Tier-1) | 60% | Conservative; published case studies cite 70–85% for insurance Tier-1 |
| A3 | Agent loaded cost | EUR 50,000/year | German agent: EUR 28–32k salary + 55–65% employer costs |
| A4 | Average contacts per day | 2,400 | 1,800 calls + 600 chats |
| A5 | Claude API cost per contact | EUR 0.013 | ~800 input + 300 output tokens × claude-opus-4-6 pricing |
| A6 | Average policy value | EUR 380 | Typical German home contents insurance annual premium |
| A7 | Churn reduction | 0.5pp | Conservative; faster response time is primary churn driver (McKinsey 2022) |
| A8 | 24/7 value | EUR 28,000/year | ~30 contacts/night × 365 × EUR 2.40 |
| A9 | No redundancies in year 1 | — | Agents redeployed to complex contacts |

### 1.6 Break-Even Point

**Monthly net benefit:** EUR 1,266,694 / 12 = EUR 105,558/month  
**Upfront investment:** EUR 33,850  
**Break-even:** EUR 33,850 / EUR 105,558 = **~9.7 days after go-live**

The investment pays back in under 10 days of operation.

---

## Part 2: Risk Assessment Matrix

**Scoring:** Likelihood 1–5 × Impact 1–5  
**Risk level:** 1–5 = Low | 6–12 = Medium | 13–25 = High

| # | Risk | Category | L | I | Score | Level | Mitigation |
|---|---|---|---|---|---|---|---|
| R1 | **AI hallucination — incorrect policy information given to customer** | Technical | 3 | 4 | 12 | 🟡 Medium | RAG architecture grounds responses in KB only; Claude instructed to admit ignorance rather than guess; ComplianceGuard reviews every reply before it is spoken; 10% QA sample review |
| R2 | **GDPR breach — conversation data mishandled** | Regulatory | 2 | 5 | 10 | 🟡 Medium | No audio stored; transcripts not persisted; Supabase call_log stores intent + timestamp only (no message content); Anthropic DPA executed; DPIA completed |
| R3 | **EU AI Act reclassification as high-risk** | Regulatory | 2 | 4 | 8 | 🟡 Medium | System scoped to information-only; no binding decisions made; human escalation always available; annual compliance review; ComplianceGuard enforces Art. 52 disclosure at runtime |
| R4 | **Biased or discriminatory responses** | Ethical | 2 | 4 | 8 | 🟡 Medium | Prompt engineering prohibits discriminatory framing; monthly bias audit on intent classification; escalation available to all users without restriction |
| R5 | **Agent adoption resistance** | Operational | 3 | 3 | 9 | 🟡 Medium | Framing: AI handles the dull calls, agents get the interesting ones; weekly feedback sessions; adoption KPI tracked |
| R6 | **API outage (Deepgram / ElevenLabs / Anthropic / Simli)** | Technical | 2 | 3 | 6 | 🟢 Low | Fallback: route all contacts to human agents; API uptime SLAs monitored; n8n health check alerting; text fallback if TTS fails |
| R7 | **Customer frustration — bot fails to understand** | Operational | 3 | 3 | 9 | 🟡 Medium | After 4 unresolved turns: auto-escalation to human agent; "speak to a person" available at every turn; no dead ends |
| R8 | **Prompt injection / jailbreak attempts** | Security | 2 | 3 | 6 | 🟢 Low | System prompt hardened; responses constrained to insurance KB; ComplianceGuard detects off-topic content; no backend system access |
| R9 | **STT quality degradation (non-native accents / browser mic)** | Technical | 3 | 2 | 6 | 🟢 Low | Documented known limitation; text input fallback always available; production deployment uses telephony audio (Twilio) not browser mic |
| R10 | **Mock CRM data treated as real** | Operational | 1 | 4 | 4 | 🟢 Low | Clearly labelled as simulation in all documentation; no real customer data in system; authentication flow to be added in Phase 2 |

### Risk Summary

| Level | Count | Risks |
|---|---|---|
| 🔴 High (13–25) | 0 | None |
| 🟡 Medium (6–12) | 5 | R1, R2, R3, R4, R5, R7 |
| 🟢 Low (1–5) | 4 | R6, R8, R9, R10 |

**Overall risk profile:** Medium. No high risks identified. The dominant risk is AI hallucination (R1) — mitigated by the RAG architecture and ComplianceGuard agent reviewing every reply before it is spoken. The project is recommended to proceed to pilot phase.

---

## Part 3: Current MVP vs Production Gap

| Dimension | Current MVP | Production requirement |
|---|---|---|
| STT input | Browser microphone | Twilio SIP telephony |
| Knowledge base | 154 synthetic FAQs, keyword search | Real policy PDFs, pgvector semantic search |
| CRM | 20 mock customers, name+policy lookup | Live policy system API, identity verification |
| Analytics | Google Sheets + Supabase logs | Live Looker Studio / Grafana dashboard |
| Routing accuracy | 83% (improving to 90%+) | ≥95% with domain fine-tuning |
| Authentication | None | PIN + date of birth verification |
| Languages | EN/DE/ES/FR/IT auto-detect | Full translation + localised KB per market |
| Deployment | Render.com free tier | Dedicated infrastructure, 99.9% SLA |

All gaps are resolvable with additional integration work. The architecture is proven.
