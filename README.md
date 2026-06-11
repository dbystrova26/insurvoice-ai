# insurvoice-ai

**AI voice agent for insurance customer service — a Parloa-style POC.**  
Ironhack AI Consulting Bootcamp — Final Project  
EU AI Act & GDPR compliant. Speech-to-text → AI reasoning → text-to-speech.

---

## What it is

InsurVoice AI is a conversational **voice agent** that answers insurance customer calls autonomously. A caller speaks, the system transcribes it, an AI agent classifies intent and answers from a knowledge base, and the response is spoken back in a natural voice. It escalates to a human agent when needed.

**The voice pipeline:**

```
🎤 Caller speaks  →  📝 Whisper (STT)  →  🧠 Claude (reasoning + RAG)  →  🔊 ElevenLabs (TTS)  →  speaker
                                                      ↓
                                          ↪️ Escalate to human if needed
```

**Inspired by:** [Parloa](https://parloa.com) — Berlin-based conversational voice AI (~$1B, Series B 2024). This POC demonstrates the same product category — voice-first customer service automation — using open tools.

**Use case:** Allianz Direct GmbH (fictional) — 1,800 calls/day, 68% Tier-1, EUR 2.1M contact centre cost. AI deflects 60%+ of Tier-1 → ~EUR 1.2M annual value.

---

## Live Demo

🚀 **[Launch InsurVoice AI on Render](https://insurvoice-ai.onrender.com)** ← update after deploy

*Enter your Anthropic, OpenAI, and ElevenLabs keys in the sidebar. First load ~30s (free tier wakes up).*

---

## Tech Stack

| Layer | Tool |
|---|---|
| Speech-to-text | OpenAI Whisper (`whisper-1`) |
| Reasoning | Anthropic Claude `claude-opus-4-6` |
| Text-to-speech | ElevenLabs (`eleven_turbo_v2_5`) |
| Knowledge | RAG over insurance FAQ base |
| Frontend | Streamlit (mic + file upload + text input) |
| Deploy | Render.com (free tier) |
| POC orchestration | Voiceflow + n8n (see `poc/`) |

---

## Project Structure

```
insurvoice-ai/
├── use_case_definition.md          # Business problem + solution
├── roi_risk_assessment.md          # ROI + 8-risk matrix
├── strategic_plan.md               # Deployment + go-to-market
├── poc/
│   ├── poc_workflow.json           # n8n workflow (importable)
│   └── poc_documentation.md        # POC walkthrough
├── compliance/
│   ├── eu_ai_act_compliance.md     # Classification + voice channel assessment
│   └── gdpr_documentation.md       # Data flows, DPIA, voice biometric analysis
├── mvp/
│   ├── app.py                      # Streamlit voice app
│   ├── voice.py                    # Whisper STT + ElevenLabs TTS
│   ├── agent.py                    # InsurVoice agent logic
│   ├── knowledge.py                # KB retrieval
│   ├── download_data.py            # Data setup (run once)
│   ├── requirements.txt
│   ├── render.yaml                 # One-click Render deploy
│   ├── .env.example
│   └── mvp_documentation.md
├── .gitignore
└── README.md
```

---

## Quick Start

```bash
git clone https://github.com/YOUR-USERNAME/insurvoice-ai.git
cd insurvoice-ai/mvp
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY
python download_data.py
streamlit run app.py
```

---

## Compliance Highlights

| Regulation | Status |
|---|---|
| EU AI Act | ✅ Limited Risk (Art. 52) — audible AI disclosure at call start |
| GDPR | ✅ Voice transcribed then discarded; not stored. Voiceprint NOT used → not Art. 9 biometric data |
| Voice-specific | ✅ DPIA covers audio-to-US-processor transfer; self-hosted Whisper recommended for production |

---

## Why Voice (vs the chat version)

Voice is Parloa's actual product. A voice demo shows the full **speech-to-text → reasoning → text-to-speech** loop that defines the conversational voice AI category. The chat version is simpler but doesn't demonstrate the capability that makes this market interesting.

---

## Author

**Daria Bystrova** · Ironhack AI Consulting Bootcamp · 2025

*Student project / proof of concept. Not affiliated with Allianz, Parloa, OpenAI, Anthropic, or ElevenLabs.*
