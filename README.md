# InsurVoice AI

![InsurVoice AI Banner](banner.png)

**AI voice agent for insurance customer service — meet Tina.**  
Ironhack AI Consulting Bootcamp · Final Project · Daria Bystrova

AI voice agent for insurance customer service built as an Ironhack AI Consulting Capstone Project. Speak naturally and Tina, a lip-synced avatar, hears you via live speech recognition (Deepgram), reasons through a multi-agent pipeline (Claude Sonnet), retrieves answers from an 87-FAQ knowledge base combined with pgvector semantic search over 5 real insurance policy PDFs, and speaks back (ElevenLabs). Every escalation automatically triggers an n8n workflow — Gmail briefing, Google Sheets log, and a Slack alert. EU AI Act Article 52 and GDPR compliant by design.

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
InsurVoiceAgent (agent.py)
    ├── retrieve_context() ── dual RAG (see below)
    ├── Claude Sonnet ─────── grounded response generation
    ├── Intent classification → routing
    └── Escalation logic ──── auto-escalate after 2 low-confidence turns
    ↓
ElevenLabs TTS ──── text → MP3 audio (eleven_turbo_v2_5)
    ↓
Browser plays MP3 via audio.onended (mic reopens exactly when audio ends)
    ↓
PCM decoded from MP3 → sent to Simli for lip-sync only (Simli audio muted)
    ↓
Simli WebRTC ────── lip-synced avatar face (LiveKit transport, Frankfurt node)
```

### Dual RAG Pipeline

```
Every customer turn → retrieve_context(query)
    │
    ├── 1. Keyword search (knowledge.py)
    │       87 FAQs in knowledge_base.json
    │       Scores by word overlap → top 2 FAQs
    │       Fast (~5ms), always runs
    │
    └── 2. pgvector semantic search (rag.py)
            embed query → OpenAI text-embedding-3-large (1536 dims)
            cosine similarity → Supabase policy_chunks table
            top 3 chunks (similarity > 0.2)
            ~250ms, finds policy-specific detail

Both results combined → injected into Claude system prompt:
    === FAQ KNOWLEDGE BASE ===
    Q: Can I pay monthly? A: Yes, with 3-5% surcharge...

    === POLICY DOCUMENT CONTEXT ===
    [Source: Home Contents Insurance | Relevance: 91%]
    Water escaping from fixed pipes is covered as Leitungswasser...
```

### Automation Layer

```
InsurVoiceAgent (on escalation)
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
| **Backend** | Flask + Flask-SocketIO (threading mode, gunicorn sync worker) |
| **Speech-to-text** | Deepgram nova-2 (live WebSocket streaming, `stream.py`) |
| **Reasoning** | Anthropic Claude Sonnet (`claude-sonnet-4-6`) |
| **Text-to-speech** | ElevenLabs `eleven_turbo_v2_5` (MP3 output) |
| **Avatar** | Simli WebRTC (lip-synced, LiveKit transport) |
| **RAG — primary** | pgvector semantic search on Supabase (`rag.py`) |
| **RAG — always-on** | 87-FAQ keyword search (`knowledge.py` + `knowledge_base.json`) |
| **Embeddings** | OpenAI `text-embedding-3-large` (1536 dims) |
| **CRM database** | Supabase PostgreSQL (`crm.py`) |
| **Automation** | n8n (Gmail + Google Sheets + Slack) |
| **Compliance** | EU AI Act Art. 52 + GDPR enforced at runtime |
| **Deployment** | Render.com (gunicorn sync worker, 100 threads) |

---

## Evaluation Results (June 2026)

Tested against 30 realistic customer questions using production `agent.py` with dual RAG active.

```
Model:   claude-sonnet-4-6
RAG:     pgvector (Supabase) + keyword fallback (knowledge_base.json)
Cases:   30
```

| Metric | Target | Result | Status |
|---|---|---|---|
| Routing accuracy | ≥ 85% | **86.7%** (26/30) | ✅ PASS |
| Keyword coverage | ≥ 70% | **85.6%** | ✅ PASS |
| Overall pass rate | — | **83.3%** | ✅ |
| Avg response time | < 8s | **4.3s** | ✅ |
| Compliance rate | 100% | **100%** | ✅ |

**Intent routing breakdown:**
- Claims (file_claim, claim_status): 4/5 correct
- Policy coverage: 9/10 correct
- Billing queries: 5/5 correct ✅
- General info: 5/5 correct ✅
- Escalation: 2/2 correct ✅

**What improved with dual RAG:**
- Billing keywords (grace period, surcharge, direct debit, portal): keyword search now always fires alongside pgvector
- Opening hours (Monday, Friday, Saturday): FAQ now found reliably
- Policy-specific terms (Leitungswasser, Elementarschäden, Tierhalterhaftpflicht): retrieved from actual PDF chunks

---

## Knowledge Base & RAG

### Two-layer retrieval — always both, not one-or-other

```python
# rag.py — retrieve_context()
def retrieve_context(query):
    # Layer 1: pgvector semantic search on 5 policy PDFs
    rag_results = semantic_search(query, n_results=3)

    # Layer 2: keyword search on 87 FAQs — always runs
    faq_context = keyword_retrieve(query, top_k=2)

    # Both combined and injected into Claude prompt
    return faq_context + rag_context
```

Previously: RAG-or-fallback (only keyword if pgvector failed)  
Now: RAG-AND-FAQ (both always, FAQs first for specificity)

### Knowledge base — 87 FAQs

`mvp/web/data/knowledge_base.json` — 87 FAQs across 6 categories:

| Category | FAQs | Key topics |
|---|---|---|
| home_insurance | 23 | Water/fire/theft/storm, Leitungswasser, electronics, vandalism |
| claims | 17 | Filing, timelines, rejection appeals, settlement, new-for-old |
| billing | 13 | Monthly/annual payment, grace period, surcharge, SEPA, discounts |
| policy | 13 | Renewal, cancellation, moving home, deductibles, cooling-off |
| general | 14 | Opening hours Mon-Fri 8-20 / Sat 9-17, portal, complaints, ombudsman |
| liability | 7 | Dog damage, child accidents, tenant liability, lawyer costs |

### Policy PDFs — 5 documents, 27 pgvector chunks

| Document | Chunks | Key content |
|---|---|---|
| Home Contents Insurance | 8 | Leitungswasser, fire, theft, sum insured, deductibles |
| Insurance Claims Guide | 5 | Filing process, timelines, documentation, settlement |
| Glass Breakage Insurance | 4 | Glasbruch extension, EUR 100 deductible |
| Extension to Home Contents Policy | 5 | Elementarschäden, flood, earthquake, natural hazards |
| Personal Liability Insurance | 5 | Haftpflicht, Tierhalterhaftpflicht, dog liability |

### Ingesting policy PDFs

```bash
cd mvp/web
python rag.py --ingest   # chunks, embeds, stores all PDFs → Supabase
python rag.py --test     # verify semantic search with 7 sample queries
```

Requires `OPENAI_API_KEY` and `DATABASE_URL` in `.env`. Run once — chunks persist in Supabase.

### Supabase schema

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

CREATE INDEX ON policy_chunks USING hnsw (embedding vector_cosine_ops);
```

---

## Audio Architecture

The avatar has two audio paths — only one plays sound:

```
Server → MP3 bytes → base64 → browser
    ├── new Audio('data:audio/mpeg;base64,...').play()    ← YOU HEAR THIS
    └── decode MP3 → PCM16 → simliClient.sendAudioData() ← lip-sync only
         (avatarAudio element permanently muted, volume=0, onplay=pause)
```

**Mic timing:** reopens via `audio.onended` — the exact moment MP3 finishes playing, not a timer. Previously used an estimated duration which caused the mic to stay closed too long, requiring 3-5 repetitions.

**Greeting delay:** 6 seconds after socket connect, giving Simli time to initialize before audio is sent.

---

## Deployment

### Render.com

| Setting | Value |
|---|---|
| Root Directory | `mvp/web` |
| Build Command | `pip install -r requirements.txt && python download_data.py` |
| Start Command | `gunicorn --worker-class sync --workers 1 --threads 100 --bind 0.0.0.0:$PORT --timeout 120 server:app` |

**Important:** Set the Start Command directly in the Render dashboard — it overrides `render.yaml`.

**render.yaml location:** `mvp/render.yaml` — Render reads this. `mvp/web/render.yaml` is ignored.

**Worker class history:** gevent (ssl recursion error) → eventlet (gunicorn 26 dropped entry point) → **sync + threads 100** (works perfectly).

### download_data.py fix

`download_data.py` runs at every build and previously overwrote `knowledge_base.json` with only 7 entries. Fixed to check if a larger KB already exists before overwriting:

```python
if out.exists():
    existing_count = len(json.loads(out.read_text())["faqs"])
    if existing_count > len(kb["faqs"]):
        log(f"Kept existing knowledge base: {existing_count} FAQ entries")
        return True
```

Build log should show: `→ Kept existing knowledge base: 87 FAQ entries`

---

## Required API Keys

Set all in Render dashboard → Environment:

| Key | Service | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude reasoning | `claude-sonnet-4-6` |
| `DEEPGRAM_API_KEY` | Live STT | nova-2 model |
| `ELEVENLABS_API_KEY` | Voice synthesis | ElevenAPI credits (pay-as-you-go, separate from subscription plan) |
| `ELEVENLABS_VOICE_ID` | Voice ID | From ElevenLabs dashboard |
| `SIMLI_API_KEY` | Avatar lip-sync | Hobby plan ($10/mo) after free 50 min |
| `SIMLI_FACE_ID` | Avatar face | From Simli dashboard |
| `OPENAI_API_KEY` | RAG embeddings | `text-embedding-3-large` for pgvector ingestion |
| `DATABASE_URL` | Supabase PostgreSQL | RAG chunks + CRM + call_log |
| `FLASK_SECRET` | Session security | Auto-generated by Render |
| `N8N_WEBHOOK_URL` | Automation | Optional — fires on escalation |

### ElevenLabs billing note

The ElevenLabs Starter plan ($6/mo) covers **ElevenAgents minutes** — not direct API calls. The `/v1/text-to-speech` endpoint draws from **ElevenAPI credits** (pay-as-you-go). Add $2–5 at **elevenlabs.io/app/subscription → ElevenAPI tab → Add credits** ($0.05 per 1K characters).

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

No eventlet or gevent — threading mode with gunicorn sync worker avoids ssl recursion errors on Render.

---

## Project Structure

```
insurvoice-ai/
├── README.md                    ← this file (only README)
├── banner.png
├── architecture.png
└── mvp/
    ├── render.yaml              ← Render reads THIS (not mvp/web/render.yaml)
    └── web/
        ├── server.py            ← Flask + SocketIO, all routes + socket events
        ├── agent.py             ← InsurVoiceAgent (Claude Sonnet, dual RAG, multi-turn)
        ├── rag.py               ← Dual retrieval: pgvector + keyword combined
        ├── knowledge.py         ← 87-FAQ keyword search
        ├── stream.py            ← DeepgramStreamSession (WebSocket STT)
        ├── voice.py             ← ElevenLabs MP3 synthesis
        ├── stt.py               ← Deepgram REST fallback
        ├── crm.py               ← Supabase CRM lookup
        ├── n8n_integration.py   ← Post-escalation webhook (threading, no gevent)
        ├── download_data.py     ← Build-time setup (preserves existing KB)
        ├── evaluate.py          ← 30-question accuracy evaluation
        ├── requirements.txt
        ├── data/
        │   ├── knowledge_base.json   ← 87 FAQs (keyword layer)
        │   └── policies/             ← 5 policy PDFs (pgvector layer)
        ├── static/
        │   ├── avatar.js
        │   └── simli-client.js       ← Simli WebRTC SDK
        └── templates/
            ├── index.html            ← Voice-only interface
            └── avatar.html           ← Tina avatar (muted Simli audio, onended mic)
```

---

## What's Working (June 2026)

| Feature | Status |
|---|---|
| Avatar loads + lip-syncs | ✅ |
| Greeting fires after 6s (Simli ready) | ✅ |
| Live mic transcription (Deepgram nova-2) | ✅ |
| Mic reopens via audio.onended (not timer) | ✅ |
| Single audio output (Simli audio permanently muted) | ✅ |
| Claude Sonnet response generation | ✅ |
| ElevenLabs voice synthesis (MP3) | ✅ |
| Dual RAG: pgvector + FAQ keyword | ✅ |
| Text input with session continuity (X-Socket-ID) | ✅ |
| Intent routing (claims/billing/policy/escalation) | ✅ |
| EU AI Act disclosure on first turn | ✅ |
| n8n webhook on escalation (threading, not gevent) | ✅ |
| knowledge_base.json preserved across deploys | ✅ |

---

## Demo Script

**Claims:**
> *"I want to file a claim for water damage"* → routes to claims, asks for policy number + photos

**RAG-grounded policy answer:**
> *"Does my policy cover burst pipes?"* → semantic search finds Leitungswasser clause from Home Contents PDF (91% match), EUR 250 deductible mentioned

**Billing (keyword FAQ):**
> *"Can I pay monthly?"* → FAQ retrieves: monthly available with 3-5% surcharge, switch at renewal

**Opening hours (keyword FAQ):**
> *"What are your opening hours?"* → Monday to Friday 8am to 8pm, Saturday 9am to 5pm

**Compliance:**
> *"Are you a real person?"* → identifies as AI (EU AI Act Art. 52)

**Escalation + n8n:**
> *"I want to speak to a human"* → transfers, fires n8n → Slack alert + Google Sheets log + Gmail briefing

---

## Sample Conversation

```
🤖 Tina   Hello, you're speaking with InsurVoice, an AI assistant for Allianz Direct.
           How can I help you today?

👤 User    My pipe burst and flooded my flat.

🤖 Tina   I'm sorry to hear that — a burst pipe is really stressful. The good news
           is this is covered under your Hausratversicherung as Leitungswasser damage.
           Your EUR 250 deductible applies. To file a claim I'll need your policy
           number, the date it happened, and photos of the damage if possible.
           [RAG: Home Contents Insurance 91% + Claims Guide 74%]

👤 User    I want to speak to a human.

🤖 Tina   Of course, I'll connect you to a colleague right away. Please hold.

↗️ Escalated  |  n8n: Slack #insurvoice-alerts + Google Sheets + Gmail briefing
```

---

## Compliance

| Regulation | Implementation |
|---|---|
| EU AI Act Art. 52 | AI identity disclosed on every first turn; enforced in `agent.py` system prompt |
| GDPR | Audio streamed then discarded; not stored; no biometric profiling |
| Data minimisation | Only intent labels logged, not message content |

---

## Author

**Daria Bystrova** · Ironhack AI Consulting Bootcamp · 2026  
GitHub: [github.com/dbystrova26/insurvoice-ai](https://github.com/dbystrova26/insurvoice-ai)

*Fictional scenario for educational purposes. Not affiliated with Allianz, Anthropic, Deepgram, ElevenLabs, Simli, Supabase, or n8n.*
