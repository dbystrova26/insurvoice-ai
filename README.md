# InsurVoice AI

[![InsurVoice AI Banner](https://github.com/dbystrova26/insurvoice-ai/raw/main/banner.png)](https://insurvoice-ai.onrender.com/avatar)

**AI voice agent for insurance customer service — meet Tina.**  
Ironhack AI Consulting Bootcamp · Final Project · Daria Bystrova

AI voice agent for insurance customer service built as an Ironhack AI Consulting Capstone Project. Speak naturally and Tina, a lip-synced avatar, hears you via live speech recognition (Deepgram nova-3), reasons through a 7-agent pipeline (Claude Sonnet 4.6), retrieves answers from an 87-FAQ knowledge base combined with pgvector semantic search over 5 real insurance policy PDFs, and speaks back (ElevenLabs). Every call is logged to Google Sheets and Supabase. Every escalation automatically triggers an n8n workflow — Gmail briefing, Google Sheets log, and a Slack alert. EU AI Act Article 52 and GDPR compliant by design.

---

## Live Demo

🎭 **[Launch Avatar Interface](https://insurvoice-ai.onrender.com/avatar)** — Tina with lip-sync

*First load ~30s on free Render tier. Tina greets you automatically after 6 seconds.*

---

## Architecture

### Voice Pipeline

```
You speak / type
    ↓
Deepgram nova-3 ── live WebSocket STT, accent-robust
    ↓
InsurVoiceAgent (agent.py)
    ├── retrieve_context() ── dual RAG (see below)
    ├── Claude Sonnet 4.6 ─── grounded response generation
    ├── Intent classification → routing
    └── Escalation logic ──── auto-escalate after 2 low-confidence turns
    ↓
ElevenLabs TTS ──── text → MP3 audio
    ↓
Browser plays MP3 via audio.onended (mic reopens exactly when audio ends)
    ↓
PCM decoded from MP3 → sent to Simli for lip-sync only (Simli audio muted)
    ↓
Simli WebRTC ────── lip-synced avatar face (LiveKit transport)
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

Both results combined → injected into Claude system prompt.
Circuit breaker: if Supabase unreachable, falls back to keyword-only gracefully.
```

### Automation Layer — n8n Workflow

Every call triggers the **Call Ended Webhook** to n8n:

```
Flask Backend
    ├── Call ends
    ├── fire_n8n_webhook() fires in background thread
    └── POST to n8n with call data
                ↓
n8n Webhook Trigger
    ├── Logs to Google Sheets (ALL calls)
    ├── Sends Customer Summary Email (ALL calls)
    └── SWITCH: "Was Escalated?"
         ├─ TRUE:
         │   ├── Agent Briefing Email → support team
         │   └── Slack Alert → #insurvoice-alerts
         └─ FALSE: (inactive)
```

---

## Automation Outputs

### 1. n8n Workflow Overview ✅

[![n8n Workflow](https://github.com/dbystrova26/insurvoice-ai/raw/main/screenshots/n8n_workflow_insurvoice.png)](https://github.com/dbystrova26/insurvoice-ai/blob/main/screenshots/n8n_workflow_insurvoice.png)

### 2. Agent Briefing Email ✅

[![Agent Briefing Email](https://github.com/dbystrova26/insurvoice-ai/raw/main/screenshots/n8n_email_agent_briefing_escalation.png)](https://github.com/dbystrova26/insurvoice-ai/blob/main/screenshots/n8n_email_agent_briefing_escalation.png)

Sent to the support team on escalation. Includes: customer details, intent, priority, handoff summary, call ID, timestamp, compliance status.

### 3. Customer Summary Email ✅

[![Customer Summary Email](https://github.com/dbystrova26/insurvoice-ai/raw/main/screenshots/n8n_customer_email.png)](https://github.com/dbystrova26/insurvoice-ai/blob/main/screenshots/n8n_customer_email.png)

Sent to customer for ALL calls. Includes: conversation summary, call details, GDPR notice, next steps.

### 4. Slack Alert ✅

[![Slack Alert](https://github.com/dbystrova26/insurvoice-ai/raw/main/screenshots/n8n_slack_alert.png)](https://github.com/dbystrova26/insurvoice-ai/blob/main/screenshots/n8n_slack_alert.png)

Posted to `#insurvoice-alerts` on escalation. Includes: call ID, customer, topic, priority, handoff summary.

### 5. Google Sheets Log ✅

ALL calls logged to `invoice-ai-data-log`. Columns: Timestamp, Call ID, Customer Name, Customer Email, Language, Intent, Route, Escalated, Resolved, Turns, Duration, Compliance, Summary.

---

## Evaluation Results (June 2026)

Tested against 30 realistic customer questions using production `agent.py` with dual RAG active.

```
Model:   claude-sonnet-4-6
RAG:     pgvector (Supabase) + keyword fallback (knowledge_base.json)
Cases:   30
```

| Metric            | Target | Result            | Status  |
| ----------------- | ------ | ----------------- | ------- |
| Routing accuracy  | ≥ 85%  | **86.7%** (26/30) | ✅ PASS |
| Keyword coverage  | ≥ 70%  | **85.6%**         | ✅ PASS |
| Overall pass rate | —      | **83.3%**         | ✅      |
| Avg response time | < 8s   | **4.3s**          | ✅      |
| Compliance rate   | 100%   | **100%**          | ✅      |

---

## Knowledge Base & RAG

### Knowledge base — 87 FAQs

`mvp/web/data/knowledge_base.json` — 87 FAQs across 6 categories:

| Category        | FAQs | Key topics                                                            |
| --------------- | ---- | --------------------------------------------------------------------- |
| home_insurance  | 23   | Water/fire/theft/storm, Leitungswasser, electronics, vandalism        |
| claims          | 17   | Filing, timelines, rejection appeals, settlement, new-for-old         |
| billing         | 13   | Monthly/annual payment, grace period, surcharge, SEPA, discounts      |
| policy          | 13   | Renewal, cancellation, moving home, deductibles, cooling-off          |
| general         | 14   | Opening hours Mon-Fri 8-20 / Sat 9-17, portal, complaints, ombudsman  |
| liability       | 7    | Dog damage, child accidents, tenant liability, lawyer costs            |

### Policy PDFs — 5 documents, 27 pgvector chunks

| Document                          | Chunks | Key content                                           |
| --------------------------------- | ------ | ----------------------------------------------------- |
| Home Contents Insurance           | 8      | Leitungswasser, fire, theft, sum insured, deductibles |
| Insurance Claims Guide            | 5      | Filing process, timelines, documentation, settlement  |
| Glass Breakage Insurance          | 4      | Glasbruch extension, EUR 100 deductible               |
| Extension to Home Contents Policy | 5      | Elementarschäden, flood, earthquake, natural hazards  |
| Personal Liability Insurance      | 5      | Haftpflicht, Tierhalterhaftpflicht, dog liability     |

### Ingesting policy PDFs

```bash
cd mvp/web
python rag.py --ingest   # chunks, embeds, stores all PDFs → Supabase
python rag.py --test     # verify semantic search with 7 sample queries
```

Requires `OPENAI_API_KEY` and `DATABASE_URL` in `.env`. Run once — chunks persist in Supabase.

---

## Audio Architecture

```
Server → MP3 bytes → base64 → browser
    ├── new Audio('data:audio/mpeg;base64,...').play()    ← YOU HEAR THIS
    └── decode MP3 → PCM16 → simliClient.sendAudioData() ← lip-sync only
         (avatarAudio element permanently muted)
```

**Lip-sync fix (June 2026):** PCM is now decoded and sent to Simli *before* `audio.play()` starts. Previously the decode happened async after playback started, causing 50–300ms lip lag.

**Greeting:** fires automatically 6 seconds after socket connect. A `greeting_sent` flag prevents duplicate greetings. Greeting words ("hello", "hi") in the first 10 seconds are suppressed to avoid double responses.

**STT debounce:** if Deepgram sends the same final transcript twice within 3 seconds, the duplicate is dropped before reaching the agent.

---

## Deployment

### Render.com

| Setting        | Value                                                                                                   |
| -------------- | ------------------------------------------------------------------------------------------------------- |
| Root Directory | `mvp/web`                                                                                               |
| Build Command  | `pip install -r requirements.txt && python ../download_data.py`                                         |
| Start Command  | `gunicorn --worker-class sync --workers 1 --threads 100 --bind 0.0.0.0:$PORT --timeout 120 server:app` |

**render.yaml location:** `mvp/render.yaml` — Render reads this. `mvp/web/render.yaml` is ignored.

### Health checks

- `/api/health` — returns API key status for all services
- `/api/ping-db` — tests Supabase connection; point UptimeRobot here (5 min interval) to prevent Render sleep and Supabase auto-pause

---

## Environment Variables (Render)

| Key                   | Service             | Notes                                                      |
| --------------------- | ------------------- | ---------------------------------------------------------- |
| `ANTHROPIC_API_KEY`   | Claude reasoning    | claude-sonnet-4-6 (override with `LLM_MODEL`)              |
| `LLM_MODEL`           | Model selection     | Default: claude-sonnet-4-6 — switch models without redeploy |
| `DEEPGRAM_API_KEY`    | Live STT            | nova-3 model                                               |
| `ELEVENLABS_API_KEY`  | Voice synthesis     | ElevenAPI credits (pay-as-you-go)                          |
| `ELEVENLABS_VOICE_ID` | Voice ID            | From ElevenLabs dashboard                                  |
| `SIMLI_API_KEY`       | Avatar lip-sync     | Hobby plan after free 50 min                               |
| `SIMLI_FACE_ID`       | Avatar face         | From Simli dashboard                                       |
| `OPENAI_API_KEY`      | RAG embeddings      | text-embedding-3-large for pgvector ingestion              |
| `DATABASE_URL`        | Supabase PostgreSQL | Use Session Pooler URL (port 5432, IPv4)                   |
| `FLASK_SECRET`        | Session security    | Any random string                                          |
| `N8N_WEBHOOK_URL`     | Automation          | Webhook URL for call logging and escalation alerts         |

**Supabase connection:** Use the **Session Pooler** URL from Supabase → Connect → Session pooler (port 5432). Direct connection and Transaction pooler have IPv6 issues on Render free tier.

---

## Supabase Schema

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

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name TEXT, email TEXT, phone TEXT,
    language TEXT, policy_number TEXT UNIQUE,
    policy_type TEXT, policy_status TEXT,
    premium_monthly NUMERIC, next_payment DATE, address TEXT
);

CREATE TABLE call_log (
    id SERIAL PRIMARY KEY,
    call_id TEXT UNIQUE,
    customer_id INTEGER REFERENCES customers(id),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    language TEXT, intent TEXT, route TEXT,
    escalated BOOLEAN, resolved BOOLEAN,
    turn_count INTEGER, duration_seconds INTEGER,
    compliance_passed BOOLEAN, urgency TEXT,
    summary TEXT, handoff_summary TEXT,
    llm_used TEXT DEFAULT 'claude-sonnet-4-6'
);

ALTER TABLE call_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON call_log FOR ALL USING (true);
```

---

## Project Structure

```
insurvoice-ai/
├── README.md
├── banner.png
├── screenshots/
│   ├── n8n_workflow_insurvoice.png
│   ├── n8n_slack_alert.png
│   ├── n8n_email_agent_briefing_escalation.png
│   └── n8n_customer_email.png
└── mvp/
    ├── render.yaml              ← Render reads THIS (not mvp/web/render.yaml)
    ├── download_data.py         ← Build-time setup (preserves 87-FAQ KB)
    └── web/
        ├── server.py            ← Flask + SocketIO, all routes + socket events
        ├── agent.py             ← InsurVoiceAgent (Claude Sonnet 4.6, multi-turn)
        ├── rag.py               ← Dual retrieval: pgvector + keyword + circuit breaker
        ├── knowledge.py         ← 87-FAQ keyword search
        ├── stream.py            ← DeepgramStreamSession (WebSocket STT)
        ├── voice.py             ← ElevenLabs MP3 synthesis
        ├── crm.py               ← Supabase CRM lookup + call_log (retry thread)
        ├── n8n_integration.py   ← Webhook + urgency assessment + summaries
        ├── evaluate.py          ← 30-question accuracy evaluation
        ├── requirements.txt
        ├── data/
        │   ├── knowledge_base.json   ← 87 FAQs (keyword layer)
        │   └── policies/             ← 5 policy PDFs (pgvector layer)
        ├── static/
        │   ├── avatar.js
        │   └── simli-client.js
        └── templates/
            ├── index.html            ← Voice-only interface
            └── avatar.html           ← Tina avatar
```

---

## What's Working (June 2026)

| Feature                                                    | Status |
| ---------------------------------------------------------- | ------ |
| Avatar loads + lip-syncs (fixed 50-300ms lag)              | ✅     |
| Single greeting per session (greeting_sent flag)           | ✅     |
| No duplicate STT responses (3s debounce)                   | ✅     |
| Live mic transcription (Deepgram nova-3)                   | ✅     |
| Mic reopens via audio.onended (not timer)                  | ✅     |
| Claude Sonnet 4.6 response generation                      | ✅     |
| Dynamic model via LLM_MODEL env var                        | ✅     |
| ElevenLabs voice synthesis (MP3)                           | ✅     |
| Dual RAG: pgvector + FAQ keyword                           | ✅     |
| RAG circuit breaker (graceful fallback on Supabase down)   | ✅     |
| 87-FAQ knowledge base preserved across deploys             | ✅     |
| Intent routing (claims/billing/policy/escalation)          | ✅     |
| EU AI Act Art. 52 disclosure on first turn                 | ✅     |
| CRM lookup by name + policy number                         | ✅     |
| call_log written to Supabase (retry thread, 20 attempts)   | ✅     |
| llm_used logged per call                                   | ✅     |
| n8n webhook fires for ALL turns                            | ✅     |
| Google Sheets logging                                      | ✅     |
| Gmail notifications (Agent briefing + Customer summary)    | ✅     |
| Slack escalation alerts                                    | ✅     |
| /api/health — API key status check                         | ✅     |
| /api/ping-db — Supabase keep-alive + circuit breaker reset | ✅     |

---

## Sample Conversation

```
🤖 Tina   Hello, you're speaking with InsurVoice, an AI assistant for Allianz Direct.
           How can I help you today?

👤 User    My pipe burst and flooded my flat.

🤖 Tina   A burst pipe is covered under your Hausratversicherung as Leitungswasser
           damage — furniture, electronics, flooring, and personal belongings.
           Your EUR 250 deductible applies. To file a claim I'll need your policy
           number, the date it happened, and photos if possible.

👤 User    I want to speak to a human.

🤖 Tina   Of course, I'll connect you to a colleague right away. Please hold.

↗️ Escalated → n8n Automation:
   ├── 📊 Google Sheets: New row logged with call_id
   ├── 📧 Agent Briefing: Email sent with handoff summary
   ├── 📧 Customer Summary: Email sent to customer
   └── 💬 Slack Alert: Posted to #insurvoice-alerts
```

---

## Compliance

| Regulation        | Implementation                                                                  |
| ----------------- | ------------------------------------------------------------------------------- |
| EU AI Act Art. 52 | AI identity disclosed on every first turn; enforced in `agent.py` system prompt |
| GDPR Art. 6(1)(b) | Audio streamed then discarded; not stored; no biometric profiling               |
| Data minimisation | Only intent labels + timestamp logged, not message content                      |
| DPIA              | Complete — residual risk: Medium (Deepgram US data transfer)                    |

---

## Author

**Daria Bystrova** · Ironhack AI Consulting Bootcamp · 2026  
GitHub: [github.com/dbystrova26/insurvoice-ai](https://github.com/dbystrova26/insurvoice-ai)

*Fictional scenario for educational purposes. Not affiliated with Allianz, Anthropic, Deepgram, ElevenLabs, Simli, Supabase, or n8n.*
