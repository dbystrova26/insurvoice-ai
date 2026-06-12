# InsurVoice AI

**AI voice agent for insurance customer service — with lip-synced avatar.**  
Ironhack AI Consulting Bootcamp · Final Project · Daria Bystrova

A multi-agent voice system: speak → transcribe → reason → comply → speak back.  
Optionally rendered as an animated avatar. EU AI Act & GDPR compliant.

---

## Live Demo

🚀 **[Launch InsurVoice AI](https://insurvoice-ai.onrender.com)** — voice interface  
🎭 **[Launch with Avatar](https://insurvoice-ai.onrender.com/avatar)** — lip-synced face

*First load ~30s on free tier.*

---

## Architecture

![InsurVoice AI System Architecture](architecture.png)

**Turn flow:**
1. **Caller speaks** → Deepgram nova-3 transcribes in real time (streaming, no button press)
2. **langdetect** identifies language (EN/DE/ES/FR/IT) from transcript
3. **Router agent** classifies intent and delegates to one specialist
4. **Specialist agent** answers using 154-FAQ knowledge base via keyword RAG (Claude claude-opus-4-6)
5. **Escalation agent** handles human handoff with a written briefing for the receiving agent
6. **Compliance Guard** inspects every reply — EU AI Act Art. 52 + GDPR — before it is spoken
7. **ElevenLabs** converts the approved text to natural speech in the detected language
8. **Simli** (optional) renders a lip-synced avatar video stream via WebRTC

---

## Demo Script

Use these phrases to show every feature of the system:

### Core voice pipeline
> *"Does my home insurance cover a burst pipe?"*

Expected: routes to **policy** specialist, answers about Leitungswasser cover, deductible

> *"How do I file a claim?"*

Expected: routes to **claims** specialist, explains three ways to file

> *"Why has my premium increased?"*

Expected: routes to **billing** specialist, explains renewal review

### Multi-language (type if STT struggles)
> *"Wie melde ich einen Schaden?"*

Expected: langdetect → German, reply in German from claims specialist

> *"¿Cómo presento una reclamación?"*

Expected: langdetect → Spanish, reply in Spanish

### Compliance Guard
> *"Are you a real person?"*

Expected: **must** identify as AI (EU AI Act Art. 52 enforcement)

> *"Is my claim definitely approved?"*

Expected: **cannot** give a binding decision — compliance guard blocks this

### Escalation
> *"I want to speak to a human agent"*

Expected: graceful escalation with written handoff briefing visible in UI

> *"I'm very frustrated with how this has been handled"*

Expected: escalation after empathetic response

### Show the pipeline trace
After any reply, the **⚙ Multi-agent pipeline** panel shows:
- Which agent was called
- What intent was classified
- Whether ComplianceGuard passed

This is the live multi-agent routing — point this out to examiners.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Speech-to-text | Deepgram nova-3 (live WebSocket streaming) |
| Language detection | langdetect (Python, client-side) |
| Reasoning / agents | Anthropic Claude claude-opus-4-6 |
| Text-to-speech | ElevenLabs (eleven_turbo_v2_5, multilingual) |
| Avatar | Simli WebRTC (lip-synced, LiveKit transport) |
| Knowledge retrieval | Keyword RAG, 154-FAQ knowledge base |
| Web interface | Flask + SocketIO + custom HTML/JS |
| Compliance | EU AI Act Art. 52 + GDPR enforced at runtime |
| Deployment | Render.com |
| POC orchestration | Voiceflow + n8n (see `poc/`) |

---

## Project Structure

```
insurvoice-ai/
├── architecture.png               # system architecture diagram
├── README.md
├── use_case_definition.md         # business case + problem statement
├── roi_risk_assessment.md
├── strategic_plan.md
├── compliance/
│   ├── eu_ai_act_compliance.md
│   └── gdpr_documentation.md
├── poc/
│   ├── poc_workflow.json
│   └── poc_documentation.md
└── mvp/
    ├── agents/                    # multi-agent system
    │   ├── orchestrator.py        # turn manager, language, history
    │   ├── router.py              # intent classification
    │   ├── specialists.py         # claims/billing/policy/general
    │   ├── escalation.py          # human handoff
    │   ├── compliance_guard.py    # EU AI Act + GDPR checker
    │   ├── base.py
    │   └── ARCHITECTURE.md
    ├── voice.py                   # ElevenLabs TTS
    ├── knowledge.py               # RAG retrieval
    ├── data/knowledge_base.json   # 154 insurance FAQs
    ├── app.py                     # Streamlit demo interface
    ├── evaluate.py                # accuracy evaluation (30 test cases)
    └── web/                       # Flask + HTML voice interface ⭐
        ├── server.py              # Flask + SocketIO, all API keys server-side
        ├── stream.py              # Deepgram nova-3 live WebSocket STT
        ├── agents/                # agent package (mirrored for Render deploy)
        ├── static/
        │   └── simli-client.js    # Simli WebRTC SDK (bundled)
        ├── templates/
        │   ├── index.html         # voice-only interface
        │   └── avatar.html        # Simli lip-synced avatar interface
        ├── data/
        │   └── knowledge_base.json
        ├── evaluate.py            # run accuracy evaluation
        ├── requirements.txt
        └── render.yaml
```

---

## Quick Start

```bash
git clone https://github.com/dbystrova26/insurvoice-ai.git
cd insurvoice-ai/mvp/web
pip install -r requirements.txt
cp .env.example .env    # fill in your API keys
python download_data.py
python server.py
```

Open **http://localhost:5000** (voice) or **http://localhost:5000/avatar** (avatar).

### Required API keys

| Key | Service | Free tier |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude reasoning | console.anthropic.com |
| `DEEPGRAM_API_KEY` | Live speech-to-text | console.deepgram.com — 12K min/month |
| `ELEVENLABS_API_KEY` | Voice synthesis | elevenlabs.io — 10K chars/month |
| `ELEVENLABS_VOICE_ID` | Your voice ID | From ElevenLabs dashboard |
| `SIMLI_API_KEY` | Avatar (optional) | simli.com — 200 min/month |
| `SIMLI_FACE_ID` | Avatar face (optional) | From Simli dashboard |

---

## Evaluation

Run the accuracy evaluation against 30 test cases:

```bash
cd mvp/web
python evaluate.py
```

Scores: routing accuracy (target ≥85%), keyword coverage (target ≥70%), compliance rate, avg latency. Results saved to `eval_results.json`.

---

## Compliance

| Regulation | Status | Implementation |
|---|---|---|
| EU AI Act Art. 52 | ✅ Limited Risk | AI identity disclosed on first turn; enforced by ComplianceGuard at runtime |
| GDPR | ✅ Compliant | Audio streamed then discarded; no storage; no biometric profiling |
| Data minimisation | ✅ Applied | Only intent labels logged, not message content |

---

## Author

**Daria Bystrova** · Ironhack AI Consulting Bootcamp · 2025  
GitHub: [github.com/dbystrova26/insurvoice-ai](https://github.com/dbystrova26/insurvoice-ai)

*Fictional scenario. Not affiliated with Anthropic, Deepgram, ElevenLabs, or Simli.*
