# InsurVoice AI — Web Interface

A polished Flask + HTML voice interface for InsurVoice AI, designed for deployment on Render.

## What it does

Open the page, then either:
- **Speak mode** — tap the orb, talk, tap to stop. It transcribes (Whisper), answers (Claude), and replies out loud (ElevenLabs).
- **Upload mode** — drop a WAV/MP3/M4A/WebM file to process pre-recorded audio.
- **Type** — a text box is always available as a fallback.

API keys live server-side and are never sent to the browser.

## Design

Original design in the enterprise conversational-AI idiom: deep-violet palette,
layered-lens logo mark, bold grotesk headline type. Not affiliated with or copied
from any specific company's brand identity.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env          # add your 3 API keys
python download_data.py       # generates the knowledge base
python server.py              # http://localhost:5000
```

## Deploy to Render

1. Push the repo to GitHub
2. Render → New → Web Service → connect repo
3. Set **Root Directory** to `mvp/web`
4. Add env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`
5. Render reads `render.yaml` and configures build + start (gunicorn) automatically
6. Public HTTPS URL in ~3 minutes — the mic works because Render provides HTTPS

## Files

| File | Purpose |
|---|---|
| `server.py` | Flask app — serves the page, runs the voice pipeline |
| `templates/index.html` | The full interface (HTML + CSS + JS, self-contained) |
| `agent.py` | InsurVoice reasoning agent |
| `voice.py` | Whisper STT + ElevenLabs TTS |
| `knowledge.py` | Knowledge base retrieval |
| `download_data.py` | Generates synthetic KB (run once) |
| `requirements.txt` | Flask, gunicorn, anthropic, requests |
| `render.yaml` | Render deployment config |
| `.env.example` | API key template |

## API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | The interface |
| `/api/health` | GET | Which keys are configured |
| `/api/voice` | POST | multipart audio → transcript + reply + audio |
| `/api/text` | POST | JSON text → reply + audio |
| `/api/reset` | POST | Clear conversation memory |

## Note on the mic

Browser microphone access requires HTTPS (or localhost). Render provides HTTPS
automatically, so the mic works on the deployed URL. If a browser blocks the mic,
Upload mode and the text box both feed the same pipeline.
