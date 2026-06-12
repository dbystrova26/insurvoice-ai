# insurvoice-ai

**AI voice agent for insurance customer service.**  
Ironhack AI Consulting Bootcamp — Final Project.  
A multi-agent voice system: live speech-to-text → routed reasoning → compliance check → text-to-speech. EU AI Act & GDPR compliant.

---

## What it is

InsurVoice AI is a conversational **voice agent** that answers insurance customer calls autonomously. A caller speaks; Deepgram transcribes the audio in real time, a router delegates the question to a specialist agent, a compliance guard checks the reply, and the answer is spoken back via ElevenLabs. It hands off to a human agent the moment one is needed.

**Use case:** Allianz Direct GmbH (fictional) — a mid-size direct insurer handling ~1,800 calls/day, 68% of them routine Tier-1 queries, at a ~EUR 2.1M annual contact-centre cost. Deflecting 60%+ of Tier-1 calls to the AI represents ~EUR 1.2M of annual value.

---

## System & Data Architecture

![InsurVoice architecture](architecture.png)

**How a turn flows:**
1. **Voice in** — the caller speaks (browser mic) or uploads an audio file. Typed input always works as a fallback.
2. **Deepgram** transcribes audio to text in real time using the nova-2 streaming model — no button press, no upload wait.
3. **Router agent** classifies the message and delegates to exactly one specialist — it triages, it does not answer.
4. **Specialist agent** (Claims / Billing / Policy / General) answers using only the knowledge base via RAG — it cannot invent policy terms or amounts.
5. **Escalation agent** takes over when a human is needed, producing the spoken handoff line and a written briefing for the agent.
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
| **Compliance Guard** | Checks every reply — AI-identity, no binding decisions, no PII read-aloud — fast deterministic rules first, LLM rewrite only if a flag fires. |
| **Orchestrator** | Runs the pipeline, keeps memory, returns an `agent_trace` the UI renders live. |

Full detail in [`mvp/agents/ARCHITECTURE.md`](mvp/agents/ARCHITECTURE.md).

---

## Live Demo

🚀 **[Launch InsurVoice AI on Render](https://insurvoice-ai.onrender.com)** ← update after deploy

*First load ~30s (free tier). Add your three API keys in `.env`.*

---

## Tech Stack

| Layer | Tool |
|---|---|
| **Speech-to-text** | Deepgram (`nova-2`, live WebSocket streaming) |
| **Reasoning / agents** | Anthropic Claude `claude-opus-4-6` |
| **Text-to-speech** | ElevenLabs (`eleven_turbo_v2_5`) |
| **Knowledge retrieval** | RAG over insurance FAQ knowledge base |
| **Web interface** | Flask + SocketIO + custom HTML (API keys server-side) |
| **Quick demo** | Streamlit (`mvp/app.py`) |
| **Deployment** | Render.com (free tier) |
| **POC orchestration** | Voiceflow + n8n (see `poc/`) |

---

## Project Structure

```
insurvoice-ai/
├── architecture.png               # system & data architecture diagram
├── banner.png                     # project banner
├── use_case_definition.md
├── roi_risk_assessment.md
├── strategic_plan.md
├── poc/
│   ├── poc_workflow.json
│   └── poc_documentation.md
├── compliance/
│   ├── eu_ai_act_compliance.md
│   └── gdpr_documentation.md
├── mvp/
│   ├── agents/                    # multi-agent system
│   │   ├── orchestrator.py
│   │   ├── router.py
│   │   ├── specialists.py
│   │   ├── escalation.py
│   │   ├── compliance_guard.py
│   │   ├── base.py
│   │   └── ARCHITECTURE.md
│   ├── voice.py                   # ElevenLabs TTS
│   ├── knowledge.py               # RAG knowledge base
│   ├── app.py                     # Streamlit interface
│   ├── download_data.py
│   ├── requirements.txt
│   └── web/                       # Flask + HTML voice interface ⭐
│       ├── server.py              # Flask + SocketIO server
│       ├── stream.py              # Deepgram live streaming STT
│       ├── agents/                # agent package copy (for Render deploy)
│       ├── templates/index.html   # purple voice UI with live trace panel
│       ├── knowledge.py
│       ├── voice.py
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
cp .env.example .env       # add your 3 keys (see below)
python download_data.py
python server.py           # http://localhost:5000
```

**Three API keys needed** (all have free tiers):

| Key | Service | Get it at |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude — reasoning | console.anthropic.com |
| `DEEPGRAM_API_KEY` | Live speech-to-text | console.deepgram.com |
| `ELEVENLABS_API_KEY` | Voice replies | elevenlabs.io/app/developers |

---

## Deploy to Render

1. Push this repo to GitHub
2. Render → New → Web Service → connect repo
3. Set **Root Directory** to `mvp/web`
4. Add the three env vars above
5. Render reads `render.yaml` — build + start configured automatically
6. Mic works on the deployed URL — Render provides HTTPS

---

## Compliance

| Regulation | Status |
|---|---|
| EU AI Act | ✅ Limited Risk (Art. 52) — audible AI disclosure at call start; enforced at runtime by the Compliance Guard |
| GDPR | ✅ Audio streamed then discarded; not stored. Voiceprint not used → not Art. 9 biometric data |
| Data handling | ✅ API keys server-side only; logs hold intent labels, not message content |

---

## Author

**Daria Bystrova** · Ironhack AI Consulting Bootcamp · 2025

*Student project / proof of concept. Allianz Direct is a fictional scenario. Not affiliated with Anthropic, Deepgram, or ElevenLabs.*
