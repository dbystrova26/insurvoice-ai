# MVP Documentation — InsurVoice AI

**File:** `mvp/mvp_documentation.md`  
**GitHub repo:** `insurvoice-ai`  
**Live demo (Render):** [https://insurvoice-ai.onrender.com](https://insurvoice-ai.onrender.com) ← update after deploy

---

## What This Is

A working, deployable **AI voice agent** for insurance customer service — the same product category as Parloa. A caller speaks (or uploads audio), the system transcribes it, an AI agent answers, and the response is spoken back in a natural voice. Escalates to a human when needed.

---

## How This Extends the POC

| Dimension | POC (Voiceflow + n8n) | MVP (Streamlit + Python) |
|---|---|---|
| Voice input | Voiceflow voice capture | Browser mic (`streamlit-mic-recorder`) + file upload fallback |
| Transcription | Whisper via n8n HTTP node | Whisper via `voice.py` |
| Reasoning | Claude via n8n | Claude via `agent.py` (with memory + auto-escalation) |
| Voice output | ElevenLabs via n8n | ElevenLabs via `voice.py`, autoplay in browser |
| Deployment | n8n cloud + Voiceflow | Single Streamlit app on Render — one public URL |
| Monitoring | Google Sheets | Built-in dashboard tab |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    INSURVOICE AI (MVP)                    │
│                      Streamlit app.py                     │
└───────────────┬──────────────────────────────────────────┘
                │
   ┌────────────▼─────────────┐
   │  Voice Call tab          │
   │  - mic recorder          │
   │  - file upload fallback  │
   │  - text fallback         │
   │  - audio autoplay        │
   └────────────┬─────────────┘
                │
   ┌────────────▼─────────────┐      ┌──────────────────┐
   │  voice.py                │      │ OpenAI Whisper   │
   │  - transcribe_whisper()  │─────▶│ (speech→text)    │
   │  - synthesize_eleven()   │      └──────────────────┘
   └────────────┬─────────────┘      ┌──────────────────┐
                │                     │ ElevenLabs       │
                │              ◀──────│ (text→speech)    │
   ┌────────────▼─────────────┐      └──────────────────┘
   │  agent.py (InsurVoice)   │      ┌──────────────────┐
   │  - intent classification │─────▶│ Anthropic Claude │
   │  - response generation   │      │ claude-opus-4-6  │
   │  - escalation logic       │     └──────────────────┘
   │  - conversation memory   │
   └────────────┬─────────────┘
                │
   ┌────────────▼─────────────┐
   │  knowledge.py            │
   │  - FAQ retrieval (RAG)   │
   └──────────────────────────┘
```

---

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI — voice call, monitoring, how-it-works tabs |
| `voice.py` | Whisper STT + ElevenLabs TTS functions, with full error handling |
| `agent.py` | InsurVoiceAgent — reasoning, memory, escalation |
| `knowledge.py` | Knowledge base retrieval |
| `download_data.py` | Generates synthetic KB + intent data (run once) |
| `requirements.txt` | Dependencies |
| `render.yaml` | Render deployment config |
| `.env.example` | API key template |

---

## Setup (Local)

```bash
git clone https://github.com/YOUR-USERNAME/insurvoice-ai.git
cd insurvoice-ai/mvp
pip install -r requirements.txt
cp .env.example .env       # add your 3 API keys
python download_data.py
streamlit run app.py        # http://localhost:8501
```

You need three API keys:
- **Anthropic** (console.anthropic.com) — reasoning
- **OpenAI** (platform.openai.com) — Whisper speech-to-text
- **ElevenLabs** (elevenlabs.io) — text-to-speech (free tier: 10k chars/month)

You can also enter keys directly in the sidebar instead of using `.env`.

---

## Deploy to Render (Free, Shareable URL)

1. Push repo to GitHub
2. render.com → New → Web Service → connect repo
3. Root directory: `mvp`
4. Add three env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`
5. Render reads `render.yaml` and configures build/start automatically
6. Public URL ready in ~3 minutes

**Note on mic in browser:** microphone capture requires HTTPS. Render provides HTTPS automatically, so the mic works on the deployed URL. On `localhost` it also works. If a browser blocks the mic, the file-upload and text fallbacks always work.

---

## How to Run It (Demo Script)

1. Open the app, enter the three API keys in the sidebar
2. Go to **🎙️ Voice Call** tab
3. Click **🔴 Start speaking**, say: *"Does my home insurance cover a burst pipe?"*, click **⏹️ Stop**
4. Watch: transcription → AI response appears → voice plays automatically
5. Speak a follow-up, then try: *"I want to talk to a person"* → escalation fires
6. Check **📊 Monitoring** for deflection rate and intent chart

If the mic doesn't work in your environment, upload a short WAV/MP3 instead, or just type — all three input methods feed the same pipeline.

---

## Error Handling

The system fails gracefully at every stage:
- No API key → clear message, no crash
- Whisper fails → error shown, conversation continues via text
- ElevenLabs fails/quota exceeded → falls back to text-only response
- Claude returns malformed JSON → safe fallback response + offer to escalate
- Audio too short/empty → friendly "didn't catch that" message

---

## Known Limitations (for Production)

| Limitation | Production solution |
|---|---|
| No real phone line | Twilio/Vonage telephony integration |
| Turn-based (no interruption) | Full-duplex streaming audio |
| Voice sent to US (OpenAI) | Self-hosted Whisper in EU region |
| Static 7-item KB | Vector DB + document ingestion pipeline |
| English only | German Whisper + German ElevenLabs voice |
| ElevenLabs free quota | Paid tier for production call volume |
| Render free tier sleeps | Paid Render/Railway for always-on |
| Keys entered in UI | Server-side key management; never client-exposed |
