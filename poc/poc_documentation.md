# POC Documentation — InsurVoice AI

**File:** `poc/poc_documentation.md`  
**POC type:** No-code / low-code voice agent  
**Stack:** Voiceflow (voice dialogue) + n8n (orchestration) + Whisper (STT) + Claude (reasoning) + ElevenLabs (TTS)

---

## Demo Recording

🎥 **Demo link:** [Insert Loom/YouTube link after recording]

**What the demo shows (2–4 minutes):**
1. Caller speaks: *"Hi, does my home insurance cover a burst pipe?"*
2. Whisper transcribes the speech to text (shown on screen)
3. Bot delivers audible AI disclosure + spoken answer via ElevenLabs voice
4. Caller speaks a follow-up: *"How long would a claim take?"*
5. Bot maintains context, answers in voice
6. Caller says: *"I'd like to speak to a person"*
7. Bot acknowledges audibly, generates handoff summary, escalates
8. n8n workflow shown firing in the background

---

## Tools Used and Why

| Tool | Role | Why chosen |
|---|---|---|
| **Voiceflow** | Voice dialogue flow — manages turns, captures audio, plays responses | Native voice support; visual builder; shareable demo; accepted by Ironhack brief |
| **OpenAI Whisper** | Speech-to-text — transcribes caller audio | Best-in-class transcription; robust to accents/noise; cheap (~$0.006/min) |
| **n8n** | Orchestration — routes between STT, Claude, TTS | Free; exportable JSON; shows automation skill |
| **Anthropic Claude** | Intent classification + response generation | Reliable structured output; strong instruction-following |
| **ElevenLabs** | Text-to-speech — speaks the AI response | Most natural-sounding TTS; low latency (turbo model); free tier 10k chars/month |

---

## What the POC Does — Step by Step

```
1. Caller speaks (Voiceflow captures audio, or browser mic in MVP)
       ↓
2. Audio sent to Whisper API → transcribed to text
       ↓
3. n8n receives {transcript, conversation_id, turn_number}
       ↓
4. n8n loads knowledge base context (RAG)
       ↓
5. n8n calls Claude API with system prompt + KB + history + transcript
       ↓
6. Claude returns JSON: {intent, confidence, response, should_escalate}
       ↓
7a. (no escalation) Response text → ElevenLabs → audio → played to caller
7b. (escalation) Generate handoff summary → notify human → transfer
       ↓
8. Turn logged (anonymised: intent + timestamp only, no audio, no transcript)
```

---

## AI Capability Demonstrated

1. **Speech recognition** — Whisper converts spoken insurance queries to text, handling natural speech, accents, and background noise
2. **Intent classification** — Claude maps the transcript to one of 8 intent categories
3. **Retrieval-Augmented Generation** — relevant FAQ content retrieved and grounded; no hallucinated policy terms
4. **Natural voice synthesis** — ElevenLabs delivers a human-sounding spoken response
5. **Multi-turn voice dialogue** — context maintained across spoken turns
6. **Escalation logic** — detects when to hand off to a human, with spoken acknowledgement + text summary

This is the complete **STT → reasoning → TTS** loop that defines the conversational voice AI category (the same loop Parloa's product is built on).

---

## n8n Workflow

The exported `poc_workflow.json` contains the orchestration: webhook trigger → KB load → prompt build → Claude call → response parse → escalation router → Whisper/ElevenLabs HTTP nodes → response/escalation return. Import via n8n Settings → Import workflow.

Note: in the POC, Voiceflow handles audio capture/playback natively. In the MVP (Streamlit), the same flow runs in Python with explicit Whisper and ElevenLabs API calls (see `mvp/voice.py`).

---

## Reproducing / Running the POC

### Prerequisites
- Voiceflow account (free) — voiceflow.com
- n8n (n8n.cloud free or Docker)
- API keys: Anthropic, OpenAI (Whisper), ElevenLabs

### Steps
1. Import `poc_workflow.json` into n8n
2. Set credentials: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`
3. Activate workflow, copy webhook URL
4. In Voiceflow: build voice flow, point API block at n8n webhook
5. Test in Voiceflow's voice preview

**Faster alternative:** run the MVP (`mvp/app.py`) which does the entire pipeline in one Streamlit app — no Voiceflow/n8n setup needed. See `mvp/mvp_documentation.md`.

---

## Known Limitations (POC vs Production)

| Limitation | Production solution |
|---|---|
| No real telephony (browser/Voiceflow only) | Twilio/Vonage SIP integration for actual phone numbers |
| Whisper latency ~1–2s | Streaming STT (Deepgram) for real-time feel |
| Voice data sent to US (OpenAI) | Self-hosted Whisper to keep audio in EU |
| Static knowledge base | Vector DB with live document ingestion |
| No barge-in (caller can't interrupt) | Full-duplex audio streaming in production telephony |
| Single language (English) | Multilingual Whisper + German ElevenLabs voice |
| ElevenLabs free-tier quota (10k chars/month) | Paid tier for production volume |
