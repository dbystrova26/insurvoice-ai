# insurvoice-ai

**AI voice agent for insurance customer service.**  
Ironhack AI Consulting Bootcamp — Final Project.  
A multi-agent voice system: speech-to-text → routed reasoning → compliance check → text-to-speech. EU AI Act & GDPR compliant.

---

## What it is

InsurVoice AI is a conversational **voice agent** that answers insurance customer calls autonomously. A caller speaks; the system transcribes the audio, a router delegates the question to a specialist agent, a compliance guard checks the reply, and the answer is spoken back in a natural voice. It hands off to a human agent the moment one is needed.

**Use case:** Allianz Direct GmbH (fictional) — a mid-size direct insurer handling ~1,800 calls/day, 68% of them routine Tier-1 queries, at a ~EUR 2.1M annual contact-centre cost. Deflecting 60%+ of Tier-1 calls to the AI represents ~EUR 1.2M of annual value.

---

## System & Data Architecture

![InsurVoice architecture](architecture.png)

**How a turn flows:**
1. **Voice in** — the caller speaks (browser mic or phone) or uploads an audio file. Typed input always works as a fallback.
2. **Whisper** transcribes the audio to text in real time.
3. **Router agent** classifies the message and delegates to exactly one specialist — it triages, it does not answer.
4. **Specialist agent** (Claims / Billing / Policy / General) answers using only the knowledge base via RAG — it cannot invent policy terms or amounts.
5. **Escalation agent** takes over instead when a human is needed, producing the spoken handoff line and a written briefing for the agent (no personal identifiers in the log).
6. **Compliance Guard** inspects every candidate reply against EU AI Act Art. 52 and GDPR — passing it through or rewriting it — *before anything is spoken to the caller*.
7. **ElevenLabs** converts the approved reply to natural speech. The caller hears it.

---

## Multi-Agent Architecture

InsurVoice is not a single agent — it is a coordinated **team of specialized subagents**:

| Agent | Responsibility |
|---|---|
| **Router** | Triages each message; delegates to the right specialist. Does not answer. |
| **Claims** | Filing claims, claim status, documents, timelines. |
| **Billing** | Premiums, invoices, payments, price changes. |
| **Policy** | Coverage, limits, renewals, cancellations. |
| **General** | Greetings, opening hours, general info. |
| **Escalation** | Human handoff line + a briefing that omits personal identifiers. |
| **Compliance Guard** | Checks every reply — AI-identity, no binding decisions, no PII read-aloud, scope — fast deterministic rules first, LLM rewrite only if a flag fires. |
| **Orchestrator** | Runs the pipeline, keeps conversation memory, returns an `agent_trace` the UI renders live. |

Full detail in [`mvp/agents/ARCHITECTURE.md`](mvp/agents/ARCHITECTURE.md).

---

## Live Demo

🚀 **[Launch InsurVoice AI on Render](https://insurvoice-ai.onrender.com)** ← update after deploy

*First load takes ~30s (free tier wakes up). Enter your three API keys in the sidebar.*

---

## Tech Stack

| Layer | Tool |
|---|---|
| Speech-to-text | OpenAI Whisper (`whisper-1`) |
| Reasoning / agents | Anthropic Claude `claude-opus-4-6` |
| Text-to-speech | ElevenLabs (`eleven_turbo_v2_5`) |
| Knowledge retrieval | RAG over insurance FAQ knowledge base |
| Web interface | Flask + custom HTML (API keys server-side) |
| Quick demo | Streamlit |
| Deployment | Render.com (free tier) |
| POC orchestration | Voiceflow + n8n (see `poc/`) |

---

## Project Structure

```
insurvoice-ai/
├── architecture.png                # system & data architecture diagram
├── banner.png                      # project banner
├── use_case_definition.md          # business problem + proposed solution
├── roi_risk_assessment.md          # ROI calculation + risk matrix
├── strategic_plan.md               # deployment roadmap + go-to-market
├── poc/
│   ├── poc_workflow.json           # n8n workflow (importable)
│   └── poc_documentation.md       # POC walkthrough + limitations
├── compliance/
│   ├── eu_ai_act_compliance.md    # risk classification + voice channel assessment
│   └── gdpr_documentation.md      # data flows, DPIA, voice biometric analysis
├── mvp/
│   ├── agents/                    # the multi-agent system
│   │   ├── __init__.py
│   │   ├── orchestrator.py        # runs the full pipeline
│   │   ├── router.py              # triage and delegation
│   │   ├── specialists.py         # claims / billing / policy / general agents
│   │   ├── escalation.py          # human handoff coordinator
│   │   ├── compliance_guard.py    # EU AI Act + GDPR guardrail layer
│   │   ├── base.py                # shared agent base class
│   │   └── ARCHITECTURE.md        # architecture write-up and extension guide
│   ├── voice.py                   # Whisper STT + ElevenLabs TTS
│   ├── knowledge.py               # knowledge base retrieval (RAG)
│   ├── app.py                     # Streamlit interface
│   ├── agent.py                   # legacy single-agent (kept for reference)
│   ├── download_data.py           # synthetic data setup (run once)
│   ├── requirements.txt
│   ├── render.yaml
│   ├── .env.example
│   └── web/                       # Flask + HTML voice interface (recommended)
│       ├── server.py              # Flask app — pipeline runs server-side
│       ├── agents/                # agent package copy (required for Render deploy)
│       ├── templates/index.html   # purple voice interface with trace panel
│       ├── requirements.txt
│       ├── render.yaml
│       └── .env.example
└── README.md
```

---

## Quick Start

```bash
git clone https://github.com/dbystrova26/insurvoice-ai.git
cd insurvoice-ai/mvp/web
pip install -r requirements.txt
cp .env.example .env           # add ANTHROPIC_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY
python download_data.py
python server.py               # opens at http://localhost:5000
```

**Or use the Streamlit version:**
```bash
cd insurvoice-ai/mvp
pip install -r requirements.txt
cp .env.example .env
python download_data.py
streamlit run app.py
```

## Deploy to Render (free, public URL)

1. Push this repo to GitHub.
2. Render → New → Web Service → connect the repo.
3. Set **Root Directory** to `mvp/web`.
4. Add three env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`.
5. Render reads `render.yaml` and configures build + start automatically.
6. The mic works on the deployed URL — Render provides HTTPS.

---

## Compliance

| Regulation | Status |
|---|---|
| EU AI Act | ✅ Limited Risk (Art. 52) — audible AI disclosure at call start; enforced at runtime by the Compliance Guard |
| GDPR | ✅ Voice transcribed then discarded; not stored. Voiceprint not used → not Art. 9 biometric data |
| Data handling | ✅ API keys server-side only; conversation logs hold intent labels, not message content |

---

## Author

**Daria Bystrova** · Ironhack AI Consulting Bootcamp · 2025

*Student project / proof of concept. Allianz Direct is a fictional scenario. Not affiliated with OpenAI, Anthropic, or ElevenLabs.*
