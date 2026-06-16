# InsurVoice AI

![InsurVoice AI Banner](banner.png)

**AI voice agent for insurance customer service — meet Tina.**
Ironhack AI Consulting Bootcamp · Final Project · Daria Bystrova

AI voice agent for insurance customer service built as an Ironhack AI Consulting Capstone Project. Speak naturally and Tina, a lip-synced avatar, hears you via live speech recognition (Deepgram), reasons through a multi-agent pipeline (Claude Sonnet), retrieves answers from a 154-FAQ knowledge base backed by pgvector semantic search over 5 real insurance policy PDFs, and speaks back (ElevenLabs). Every escalation automatically triggers an n8n workflow — Gmail briefing, Google Sheets log, and a Slack alert. EU AI Act Article 52 and GDPR compliant by design.

---

## Live Demo

🎭 **[Launch Avatar Interface](https://insurvoice-ai.onrender.com/avatar)** — Tina with lip-sync

*First load ~30s on free Render tier. Tina greets you automatically after 6 seconds.*

---

## Architecture

![System Architecture](architecture.png)

### Voice Pipeline

```
You speak / type
    ↓
Deepgram nova-2 ── live WebSocket STT, accent-robust
    ↓
InsurVoice Agent
    ├── rag.retrieve_context() ── pgvector semantic search (Supabase)
    │       └── fallback: knowledge.retrieve_context() ── 154-FAQ keyword search
    ├── Claude Sonnet ─────────── grounded response generation
    └── Escalation logic ─────── auto-escalate after 2 low-confidence turns
    ↓
ElevenLabs TTS ──── text → MP3 audio (eleven_turbo_v2_5)
    ↓
Browser plays MP3 + sends PCM to Simli for lip-sync
    ↓
Simli WebRTC ────── lip-synced avatar face (LiveKit transport)
    ↓
Mic reopens exactly when audio finishes (audio.onended)
```

### RAG Pipeline

```
INGESTION (run once: python rag.py --ingest)
────────────────────────────────────────────
5 Policy PDFs
    ↓ pdfplumber extracts text
    ↓ chunk_text() — Q&A-aware chunking (300 words, 60 overlap)
    ↓ embed_text_simple() — OpenAI text-embedding-3-large (1536 dims)
    ↓ Supabase pgvector — policy_chunks table with HNSW index

RETRIEVAL (every customer turn)
────────────────────────────────────────────
Customer query
    ↓ embed query with text-embedding-3-large
    ↓ cosine similarity search → top 4 chunks (similarity > 0.2)
    ↓ format_rag_context() — [Source: doc | Relevance: 87%] + chunk text
    └── if Supabase unavailable → keyword fallback (knowledge.py)
    ↓
Context injected into Claude system prompt
    ↓
Policy-grounded response (no hallucination)
```

### Automation Layer

```
InsurVoice Agent (on escalation)
    ↓ n8n webhook, non-blocking background thread
n8n Workflow
    ├── Google Sheets ── logs escalated call
    ├── Gmail ────────── sends agent briefing email
    └── Slack ────────── posts to #insurvoice-alerts with urgency
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Flask + Flask-SocketIO (threading mode) |
| **Speech-to-text** | Deepgram nova-2 (live WebSocket streaming) |
| **Reasoning** | Anthropic Claude Sonnet (`claude-sonnet-4-6`) |
| **Text-to-speech** | ElevenLabs `eleven_turbo_v2_5` (MP3 output) |
| **Avatar** | Simli WebRTC (lip-synced, LiveKit transport) |
| **RAG — primary** | pgvector semantic search on Supabase (`rag.py`) |
| **RAG — fallback** | 154-FAQ keyword search (`knowledge.py`) |
| **Embeddings** | OpenAI `text-embedding-3-large` (1536 dims) |
| **CRM database** | Supabase PostgreSQL (`crm.py`) |
| **Automation** | n8n (Gmail + Google Sheets + Slack) |
| **Compliance** | EU AI Act Art. 52 + GDPR enforced at runtime |
| **Deployment** | Render.com (gunicorn sync worker, 100 threads) |

---

## What's Working (as of June 2026)

| Feature | Status |
|---|---|
| Avatar loads + lip-syncs | ✅ |
| Greeting fires after 6s delay | ✅ |
| Live mic transcription (Deepgram) | ✅ |
| Claude Sonnet response generation | ✅ |
| ElevenLabs voice synthesis | ✅ |
| RAG via pgvector (Supabase) | ✅ |
| Keyword fallback if RAG unavailable | ✅ |
| Single audio output (no double voice) | ✅ |
| Mic reopens exactly when audio ends | ✅ |
| Text input with session continuity | ✅ |
| Intent routing (claims, billing, policy, escalation) | ✅ |
| EU AI Act disclosure on first turn | ✅ |
| n8n webhook on escalation | ✅ |

---

## Knowledge Base & RAG

### Two-layer retrieval

`rag.py` is the primary retrieval engine. `knowledge.py` is the fallback. `agent.py` imports from `rag` — which automatically falls back to `knowledge` if Supabase is unreachable or returns no results.

```python
# agent.py
from rag import retrieve_context   # primary: pgvector
                                   # auto-fallback: keyword (knowledge.py)
```

### Policy documents (5 PDFs, ~58 pages)

| Document | FAQs | Topics |
|---|---|---|
| Home Contents Insurance | 54 | Fire, water, theft, electrical, deductibles |
| Claims Guide | 32 | Filing, documentation, timelines, status |
| Glass Breakage Extension | 18 | Coverage, deductibles, emergency boarding |
| Natural Hazards Extension | 28 | Flooding, earthquakes, landslides, snow |
| Personal Liability Insurance | 42 | Third-party damage, dog liability |

**Total: 154 FAQs across 5 documents**

### Chunking strategy

Policies are chunked into discrete Q&A pairs rather than arbitrary text segments:

1. Detect Q&A structure in policy appendices — split on `Q:` markers
2. Merge short pairs, split long ones (target ~300 words)
3. Add policy-specific metadata prefix before embedding for domain context:
   ```
   [Context: German home contents insurance Hausratversicherung covering fire 
    water damage burst pipe storm theft...] {chunk text}
   ```
4. Store with `document`, `chunk_index`, `content`, `embedding` in Supabase

### Ingesting policy PDFs

```bash
cd mvp/web
python rag.py --ingest   # chunks, embeds, stores all PDFs in data/policies/
python rag.py --test     # verify semantic search is working
```

Requires `OPENAI_API_KEY` and `DATABASE_URL` (Supabase) in `.env`.

### Supabase schema for RAG

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE policy_chunks (
    id SERIAL PRIMARY KEY,
    document VARCHAR(255),
    chunk_index INTEGER,
    content TEXT,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON policy_chunks
USING hnsw (embedding vector_cosine_ops);
```

### How retrieval works at query time

```
Customer: "Does my insurance cover burst pipes?"
    ↓
embed_text_simple("Does my insurance cover burst pipes?")
    ↓ 1536-dim vector
    ↓
SELECT content, 1 - (embedding <=> query_vec) AS similarity
FROM policy_chunks
ORDER BY embedding <=> query_vec
LIMIT 4
    ↓
[Source: Home Contents Insurance | Relevance: 91%]
"Water escaping from fixed water supply pipes is covered as
 Leitungswasser damage. EUR 250 deductible per event..."

[Source: Claims Guide | Relevance: 74%]
"To file a water damage claim, photograph the damage..."
    ↓
Injected into Claude system prompt as POLICY DOCUMENT CONTEXT
    ↓
Claude generates grounded, policy-accurate response
```

---

## Audio Architecture

The avatar has two audio paths — only one plays sound:

```
Server → MP3 bytes → base64 → browser
    ├── new Audio('data:audio/mpeg;base64,...').play()    ← YOU HEAR THIS
    └── decode MP3 → PCM16 → simliClient.sendAudioData() ← lip-sync only
         (avatarAudio element is permanently muted)
```

The mic reopens via `audio.onended` — the exact moment playback finishes, not a timer.

---

## Deployment

### Render.com

**Root Directory:** `mvp/web`  
**Build Command:** `pip install -r requirements.txt && python download_data.py`  
**Start Command:** `gunicorn --worker-class sync --workers 1 --threads 100 --bind 0.0.0.0:$PORT --timeout 120 server:app`

Set the Start Command directly in the Render dashboard — it overrides `render.yaml`.

### render.yaml location

`mvp/render.yaml` — Render reads this file. `mvp/web/render.yaml` is ignored.

---

## Required API Keys

| Key | Service | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude reasoning | `claude-sonnet-4-6` |
| `DEEPGRAM_API_KEY` | Live STT | nova-2 model |
| `ELEVENLABS_API_KEY` | Voice synthesis | Needs ElevenAPI credits (pay-as-you-go, separate from subscription) |
| `ELEVENLABS_VOICE_ID` | Voice ID | From ElevenLabs dashboard |
| `SIMLI_API_KEY` | Avatar lip-sync | Hobby plan ($10/mo) needed after free 50 min |
| `SIMLI_FACE_ID` | Avatar face | From Simli dashboard |
| `OPENAI_API_KEY` | RAG embeddings | `text-embedding-3-large` for pgvector |
| `DATABASE_URL` | Supabase PostgreSQL | RAG + CRM + call_log |
| `FLASK_SECRET` | Session security | Auto-generated by Render |
| `N8N_WEBHOOK_URL` | Automation | Optional |

### ElevenLabs billing note

The Starter plan ($6/mo) covers ElevenAgents — **not** direct API credits. Add $2–5 at **elevenlabs.io/app/subscription** → ElevenAPI tab → Add credits ($0.05/1K chars).

---

## Requirements

```
flask>=3.0
flask-socketio>=5.3
simple-websocket>=0.10
requests>=2.31
python-dotenv>=1.0
gunicorn>=21.2
anthropic>=0.25.0
websockets>=12.0
psycopg2-binary>=2.9
openai>=1.0
pdfplumber>=0.10
```

No eventlet or gevent — threading mode with gunicorn sync worker avoids the ssl recursion errors those cause on Render.

---

## Project Structure

```
insurvoice-ai/
├── mvp/
│   ├── render.yaml              ← Render reads THIS file
│   └── web/
│       ├── server.py            ← Flask + SocketIO, all routes + socket events
│       ├── agent.py             ← InsurVoiceAgent (imports from rag, falls back to knowledge)
│       ├── rag.py               ← pgvector semantic search + ingestion pipeline
│       ├── knowledge.py         ← 154-FAQ keyword fallback
│       ├── stream.py            ← DeepgramStreamSession (WebSocket STT)
│       ├── voice.py             ← ElevenLabs MP3 synthesis
│       ├── stt.py               ← Deepgram REST (single utterance fallback)
│       ├── crm.py               ← Supabase CRM lookup
│       ├── n8n_integration.py   ← Post-escalation webhook trigger
│       ├── download_data.py     ← Build-time data setup
│       ├── evaluate.py          ← 30-question accuracy evaluation
│       ├── requirements.txt
│       ├── data/
│       │   ├── knowledge_base.json   ← 154 FAQs (keyword fallback)
│       │   └── policies/             ← Policy PDFs for RAG ingestion
│       ├── static/
│       │   ├── avatar.js
│       │   └── simli-client.js       ← Simli WebRTC SDK
│       └── templates/
│           ├── index.html            ← Voice-only interface
│           └── avatar.html           ← Tina avatar interface
```

---

## Evaluation

```bash
cd mvp/web
python evaluate.py
```

Tests 30 realistic customer questions:

| Metric | Target | Result |
|---|---|---|
| Routing accuracy | ≥ 85% | 96.7% ✅ |
| Keyword coverage | ≥ 70% | 81.1% ✅ |
| Compliance rate | 100% | 100% ✅ |
| Avg response time | < 8s | 5.9s ✅ |

Results saved to `eval_results.json`.

---

## Demo Script

**Claims:**
> *"I want to file a claim"* → routes to claims, asks for policy number

**Policy (RAG-grounded):**
> *"Does my policy cover burst pipes?"* → semantic search finds water damage chunk from Home Contents PDF, answers with EUR 250 deductible

**Compliance:**
> *"Are you a real person?"* → Tina identifies as AI (EU AI Act Art. 52)

**Escalation + n8n:**
> *"I want to speak to a human"* → transfers, fires n8n webhook → Slack + email

---

## Sample Conversation

```
🤖 Tina   Hello, you're speaking with InsurVoice, an AI assistant for Allianz Direct.
           How can I help you today?

👤 User    Does my home insurance cover water damage from a burst pipe?

🤖 Tina   Yes — burst pipe damage is covered as Leitungswasser damage under your
           home contents policy. It covers furniture, electronics, and personal
           belongings. Your EUR 250 deductible applies per claim event.

           [RAG source: Home Contents Insurance | Relevance: 91%]

👤 User    I want to speak to a human.

🤖 Tina   Of course, connecting you now. Please hold for a moment.

↗️ Escalated  |  n8n: Slack alert + Google Sheets log + Gmail briefing
```

---

## Compliance

| Regulation | Implementation |
|---|---|
| EU AI Act Art. 52 | AI identity disclosed on first turn; enforced in `agent.py` |
| GDPR | Audio streamed then discarded; not stored; no biometric profiling |
| Data minimisation | Only intent labels logged, not message content |

---

## Author

**Daria Bystrova** · Ironhack AI Consulting Bootcamp · 2026  
GitHub: [github.com/dbystrova26/insurvoice-ai](https://github.com/dbystrova26/insurvoice-ai)

*Fictional scenario for educational purposes. Not affiliated with Allianz, Anthropic, Deepgram, ElevenLabs, Simli, Supabase, or n8n.*
