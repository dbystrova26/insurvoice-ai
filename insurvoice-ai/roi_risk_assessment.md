# ROI & Risk Assessment — InsurVoice AI

**Project:** InsurVoice AI — Conversational AI Customer Service Agent  
**Author:** Daria Bystrova | Ironhack AI Consulting Bootcamp | June 2025

---

## Part 1: ROI Analysis

### 1.1 Upfront Cost Estimate

| Item | Cost (EUR) | Basis |
|---|---|---|
| Solution design & consulting (this project) | 12,000 | 160h @ EUR 75/h |
| Voiceflow enterprise setup & dialogue build | 3,500 | 2 months Voiceflow Pro + setup time |
| n8n self-hosted server setup (AWS/Railway) | 800 | One-time infrastructure config |
| Claude API integration & testing | 2,000 | ~25h developer time |
| Knowledge base creation & QA | 3,000 | Content review, FAQ writing, 40h |
| Staff training (agents + QA team, 12 people) | 2,400 | 4h per person @ EUR 50/h loaded |
| Legal / compliance review (GDPR + EU AI Act) | 2,500 | ~12h external counsel |
| Contingency (15%) | 3,930 | Standard project buffer |
| **TOTAL UPFRONT** | **30,130** | |

### 1.2 Ongoing Annual Costs

| Item | Annual (EUR) | Basis |
|---|---|---|
| Anthropic Claude API | 4,800 | ~1,000 contacts/day × 365 × EUR 0.013 avg cost |
| Voiceflow Pro licence | 2,388 | EUR 199/month |
| Railway / cloud hosting (n8n + app) | 720 | EUR 60/month |
| Maintenance & prompt tuning (20h/year) | 1,500 | EUR 75/h |
| QA monitoring & audit (10% sample review) | 2,600 | 0.5h/day agent time |
| **TOTAL ANNUAL** | **12,008** | |

### 1.3 Business Value Estimate

**Baseline (current state):**
- 42 agents × EUR 50,000 loaded cost = EUR 2,100,000/year total contact centre cost
- 2,400 contacts/day × 365 = 876,000 contacts/year
- Cost per contact: EUR 2.40
- Tier-1 contacts (68%): 595,680/year — currently handled by humans at full cost

**After AI deployment (target: 60% deflection of Tier-1 contacts):**
- AI deflects: 595,680 × 60% = **357,408 contacts/year** handled autonomously
- Cost per AI-handled contact: EUR 0.013 (API) + EUR 0.004 (infra) ≈ **EUR 0.017**
- Cost saving per deflected contact: EUR 2.40 − EUR 0.017 = **EUR 2.383**
- **Annual saving from deflection: EUR 357,408 × EUR 2.383 = EUR 851,694**

**Additional value streams:**
- Reduced overtime / peak staffing (agents no longer overwhelmed): EUR 45,000/year
- CSAT improvement → reduced churn (0.5pp churn reduction × 180,000 policyholders × EUR 380 avg policy value): EUR 342,000/year (conservative)
- 24/7 availability (outside 8am–8pm current hours): new contacts handled; estimated EUR 28,000/year

**Total annual value: EUR 1,266,694**

### 1.4 ROI Calculation

**Formula:** ROI = (Net Benefit / Total Cost) × 100

| Period | Total Cost | Total Value | Net Benefit | ROI |
|---|---|---|---|---|
| **12 months** | EUR 42,138 (upfront + year 1 running) | EUR 1,266,694 | EUR 1,224,556 | **2,905%** |
| **36 months** | EUR 54,154 (upfront + 3 years running) | EUR 3,800,082 | EUR 3,745,928 | **6,916%** |

### 1.5 Assumptions Table

| # | Assumption | Value | Justification |
|---|---|---|---|
| A1 | Tier-1 contact rate | 68% | Estimated from Allianz Direct call analysis; consistent with industry benchmarks (Gartner 2023: 65–72% for insurance) |
| A2 | AI deflection rate of Tier-1 | 60% | Conservative; Parloa published case studies cite 70–85% for insurance Tier-1. 60% used for year 1. |
| A3 | Agent loaded cost | EUR 50,000/year | German contact centre agent: EUR 28–32k salary + 55–65% employer costs |
| A4 | Average contacts per day | 2,400 | 1,800 calls + 600 chats per day as stated in company profile |
| A5 | Claude API cost per contact | EUR 0.013 | ~800 input tokens + 300 output tokens × claude-opus-4-6 pricing |
| A6 | Average policy value for churn calc | EUR 380 | Typical German home + contents insurance annual premium |
| A7 | Churn reduction | 0.5 percentage points | Conservative; faster response time is primary churn driver in insurance (McKinsey 2022) |
| A8 | 24/7 value | EUR 28,000/year | Estimated 30 contacts/night × 365 × EUR 2.40 |
| A9 | No redundancies in year 1 | — | Agents redeployed to complex contacts; headcount reduction optional in Phase 3 |

### 1.6 Break-Even Point

**Monthly net benefit:** EUR 1,266,694 / 12 = EUR 105,558/month  
**Upfront investment:** EUR 30,130  
**Break-even:** EUR 30,130 / EUR 105,558 = **~8.6 days after go-live**

The investment pays back in under 9 days of operation. This is because the value stream (deflected contacts) begins generating savings immediately from day one of deployment.

---

## Part 2: Risk Assessment Matrix

**Scoring:** Likelihood 1–5 (1=very unlikely, 5=very likely) × Impact 1–5 (1=negligible, 5=severe)  
**Risk level:** 1–5 = Low | 6–12 = Medium | 13–25 = High

### Risk Matrix

| # | Risk | Category | L | I | Score | Level | Mitigation |
|---|---|---|---|---|---|---|---|
| R1 | **AI hallucination — incorrect policy information given to customer** | Technical | 3 | 4 | 12 | 🟡 Medium | RAG architecture grounds responses in KB only; Claude instructed to admit ignorance rather than guess; QA 10% sample review; all outputs include disclaimer that agent should verify with a specialist |
| R2 | **GDPR breach — conversation data mishandled or leaked** | Regulatory | 2 | 5 | 10 | 🟡 Medium | No personal data stored beyond session; Anthropic DPA executed; conversation logs anonymised; DPIA completed; data retention policy: 30 days maximum for logs |
| R3 | **EU AI Act reclassification as high-risk** | Regulatory | 2 | 4 | 8 | 🟡 Medium | System explicitly scoped to information-only; no binding decisions made; human escalation always available; annual compliance review; legal counsel engaged |
| R4 | **Biased or discriminatory responses to certain customer groups** | Ethical | 2 | 4 | 8 | 🟡 Medium | Prompt engineering prohibits discriminatory framing; monthly bias audit on intent classification across demographic proxies; escalation available to all users without restriction |
| R5 | **Agent adoption resistance — human agents distrust or undermine the system** | Operational | 3 | 3 | 9 | 🟡 Medium | Co-design pilot with 4 champion agents; framing: AI handles the dull calls, agents get the interesting ones; weekly feedback sessions; adoption KPI tracked |
| R6 | **Voiceflow / n8n / Anthropic API outage** | Technical | 2 | 3 | 6 | 🟢 Low | Fallback: route all contacts to human agents (existing state); API uptime SLAs: Anthropic 99.9%, Voiceflow 99.5%; alerting via n8n health check |
| R7 | **Customer frustration — bot fails to understand, customer trapped** | Operational | 3 | 3 | 9 | 🟡 Medium | Hard rule: after 2 failed intent classifications in a row, auto-escalate to human; "speak to a person" available at every turn; no dead ends in dialogue flow |
| R8 | **Misuse — customers attempting prompt injection or jailbreak** | Ethical | 2 | 3 | 6 | 🟢 Low | System prompt hardened against injection; responses constrained to KB; output monitored; no access to backend systems in POC/Phase 1 |

### Risk Summary

| Level | Count | Risks |
|---|---|---|
| 🔴 High (13–25) | 0 | None |
| 🟡 Medium (6–12) | 6 | R1, R2, R3, R4, R5, R7 |
| 🟢 Low (1–5) | 2 | R6, R8 |

**Overall risk profile:** Medium. No high risks identified. The dominant risk is AI hallucination (R1) — mitigated by the RAG architecture which prevents the model generating unsupported claims. The project is recommended to proceed.
