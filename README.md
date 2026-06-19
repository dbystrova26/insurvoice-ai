# InsurVoice AI

[![InsurVoice AI Banner](https://github.com/dbystrova26/insurvoice-ai/raw/main/banner.png)](https://insurvoice-ai.onrender.com/avatar)

**AI voice agent for insurance customer service — meet Tina.**  
Ironhack AI Consulting & Integration Bootcamp · Final Project · Daria Bystrova · Berlin 2026

---

Tina is a lip-synced AI voice agent that handles insurance customer service calls end-to-end. Speak naturally — Tina hears you via live speech recognition (Deepgram nova-3), reasons through a **7-agent pipeline** (Claude Sonnet 4.6), retrieves grounded answers via **Dual RAG** (87-FAQ keyword layer + pgvector semantic search over 5 real policy PDFs), and speaks back in her own voice (ElevenLabs TTS). Every call is logged to Supabase and Google Sheets. Every escalation automatically triggers an **n8n automation workflow** — Gmail briefing to the CS agent, summary email to the customer, and a Slack alert. EU AI Act Article 52 and GDPR compliant by design.

---

## 🎭 Live Demo

**[Launch Tina — insurvoice-ai.onrender.com/avatar](https://insurvoice-ai.onrender.com/avatar)**

*First load ~30s on free Render tier. Tina greets you automatically after 6 seconds.*

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [7-Agent Pipeline](#7-agent-pipeline)
3. [Dual RAG System](#dual-rag-system)
4. [Supabase Data Layer](#supabase-data-layer)
5. [n8n Automation](#n8n-automation)
6. [Voice Pipeline](#voice-pipeline)
7. [Evaluation Results](#evaluation-results)
8. [Knowledge Base & Policy PDFs](#knowledge-base--policy-pdfs)
9. [Compliance](#compliance)
10. [Deployment](#deployment)
11. [Project Structure](#project-structure)

---

## Architecture Overview

```
Customer speaks / types
        │
        ▼
  Deepgram nova-3  ──── live WebSocket STT
        │
        ▼
  ┌─────────────────────────────────────────┐
  │           7-AGENT PIPELINE              │
  │                                         │
  │  Router → KnowledgeBase + PolicyRAG     │
  │        → CRM → ResponseGenerator        │
  │        → ComplianceGuard                │
  │        → EscalationManager (if needed)  │
  └─────────────────────────────────────────┘
        │
        ▼
  ElevenLabs TTS ──── text → MP3 audio
        │
        ├── Browser plays MP3 (customer hears Tina)
        └── PCM → Simli WebRTC (lip-sync only, avatar audio muted)
        │
        ▼
  Supabase ──── call_log + CRM written
        │
        ▼
  n8n Webhook ──── Google Sheets · Gmail · Slack
```

---

## 7-Agent Pipeline

Every customer turn passes through a structured chain of specialist agents. No single prompt does everything — each agent has one job and one failure mode, which makes the system testable, auditable, and independently improvable.

### Agent 1 — Router

**File:** `agent.py` (intent classification logic)

Reads the transcribed customer message and classifies intent into one of five routes: `claims`, `policy`, `billing`, `general`, or `escalation`. All subsequent agents receive this classification.

- **Why separate:** routing accuracy (83.3–86.7% in eval) can be measured and improved independently of response quality
- **Eval result:** 86.7% routing accuracy across 30 test cases (target: ≥85%) ✅

### Agent 2 — KnowledgeBase

**File:** `knowledge.py`

Keyword-searches 87 curated insurance FAQs in `knowledge_base.json`. Scores entries by word overlap and returns the top 2 matches. Fast (~5ms), deterministic, zero embedding cost.

- **Why separate:** FAQ retrieval is a different task from semantic search — mixing them into one retrieval step forces a choice between speed and coverage
- **Eval result:** 85.6% keyword coverage ✅

### Agent 3 — PolicyRAG

**File:** `rag.py`

Embeds the customer query using `text-embedding-3-large` (1536 dimensions) and runs cosine similarity search against 27 policy PDF chunks stored in Supabase pgvector. Returns top 3 chunks (similarity > 0.2). Handles policy-specific questions that no FAQ can pre-answer.

- **Why separate:** semantic search is slower (~250ms) and costs tokens — running it only when needed keeps latency low
- **Circuit breaker:** if Supabase is unreachable, falls back gracefully to keyword-only mode

### Agent 4 — CRM

**File:** `crm.py`

Looks up the caller in the Supabase `customers` table by name or policy number. Injects their cover type, policy number, and account details into Claude's context so Tina gives a personalised answer rather than a generic clause.

- **Why separate:** personalisation logic is independent of retrieval logic — the CRM agent can be replaced with a live insurer API without touching RAG

### Agent 5 — ResponseGenerator

**File:** `agent.py` (Claude API call)

The single Claude Sonnet 4.6 call. Receives: router classification, KnowledgeBase FAQ matches, PolicyRAG chunks, CRM customer context, and conversation history. Drafts the customer-facing reply. This is the only agent that calls the LLM for generation — every other agent feeds it structured data.

- **Avg latency:** 4.3s end-to-end ✅ (target: <8s)

### Agent 6 — ComplianceGuard

**File:** `agent.py` (system prompt enforcement)

Reviews every draft reply before ElevenLabs speaks it. Enforces:
- EU AI Act Art. 52(1) — AI identity disclosure on every first turn
- No binding claims decisions — cannot accept or reject a claim
- No premium commitments
- Blocks responses that obscure AI nature

- **Eval result:** 100% compliance rate across 30 test cases ✅
- **Why separate:** compliance must run *after* generation and *before* audio synthesis — impossible to enforce if combined with the generation step

### Agent 7 — EscalationManager

**File:** `n8n_integration.py`

Fires after 2 unresolved turns or on explicit customer request. Writes the `call_log` row to Supabase, assesses urgency, generates a handoff summary, and triggers the n8n webhook — Slack alert, agent briefing email, customer summary email, Google Sheets log.

- **Why separate:** escalation is orchestration and side-effect logic, not language generation — mixing it into the response loop makes every normal call pay its overhead

---

## Dual RAG System

Every customer query triggers both retrieval layers in parallel. Results are merged and injected into Claude's context before ResponseGenerator runs.

```
Customer query
      │
      ├── Layer 1: Keyword Search (knowledge.py)
      │      87 FAQs in knowledge_base.json
      │      Word-overlap scoring → top 2 FAQs
      │      ~5ms · always runs · deterministic
      │
      └── Layer 2: pgvector Semantic Search (rag.py)
             embed query → text-embedding-3-large (1536 dims)
             cosine similarity → Supabase policy_chunks
             top 3 chunks (similarity > 0.2)
             ~250ms · finds policy-specific clauses

Both results → merged context → Claude ResponseGenerator
```

**Why two layers instead of one:**

| Situation | Layer 1 (keyword) | Layer 2 (pgvector) |
|-----------|-------------------|--------------------|
| "Can I pay monthly?" | ✅ FAQ match, instant | Less precise |
| "Does Leitungswasser damage cover my flooring?" | ❌ No keyword match | ✅ Retrieves exact policy clause |
| "What's the deductible for burst pipe?" | Partial match | ✅ EUR 250, from PDF |

Keyword handles known FAQ patterns fast and free. pgvector handles everything else semantically. Neither alone gives full coverage.

### Ingesting policy PDFs

```bash
cd mvp/web
python rag.py --ingest   # chunks, embeds, stores all PDFs → Supabase
python rag.py --test     # verify semantic search with 7 sample queries
```

Requires `OPENAI_API_KEY` and `DATABASE_URL` in `.env`. Run once — chunks persist in Supabase.

---

## Supabase Data Layer

Supabase (Postgres + pgvector) serves three distinct purposes in InsurVoice. One database, three jobs.

### Table 1 — `policy_chunks` (Vector Store)

Stores 27 PDF chunks as `vector(1536)` embeddings. Queried by PolicyRAG agent via cosine similarity.

```sql
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

**Why Supabase for vectors:** pgvector runs inside Postgres — same database, same connection string, zero extra infrastructure. No separate Pinecone or Weaviate instance needed.

### Table 2 — `customers` (CRM Mock)

Holds 20 mock customer records used by the CRM agent for personalised responses. Phase 2 replaces this with a live insurer API.

```sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name TEXT, email TEXT, phone TEXT,
    language TEXT, policy_number TEXT UNIQUE,
    policy_type TEXT, policy_status TEXT,
    premium_monthly NUMERIC, next_payment DATE, address TEXT
);
```

### Table 3 — `call_log` (Compliance Audit Trail)

Every session writes one row. Stores structured metadata only — no message content, no audio, no PII beyond what's operationally necessary. Satisfies GDPR Art. 30 record-of-processing requirement. Right to erasure = one `DELETE` query.

```sql
CREATE TABLE call_log (
    id SERIAL PRIMARY KEY,
    call_id TEXT UNIQUE,                -- UUID, key for Art. 17 deletion
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

**Why Supabase specifically:**
- pgvector, CRM, and compliance log in one Postgres instance — one connection string
- EU region available (Frankfurt) — data stays in EU, GDPR by design
- Open-source, free tier sufficient for POC — no vendor lock-in
- Row Level Security built-in for compliance

---

## n8n Automation

Every call end fires a webhook to n8n. The automation runs in a background thread so it never blocks the voice pipeline.

```
Flask backend (n8n_integration.py)
    │
    └── fire_n8n_webhook() ── background thread
                │
                ▼
        n8n Webhook Trigger
                │
                ├── Google Sheets ── log ALL calls
                │   Columns: Timestamp · Call ID · Customer · Language ·
                │             Intent · Route · Escalated · Resolved ·
                │             Turns · Duration · Compliance · Summary
                │
                ├── Customer Summary Email ── ALL calls
                │   Includes: conversation summary · call details ·
                │             GDPR notice · next steps
                │
                └── SWITCH: escalated?
                     │
                     ├─ YES:
                     │   ├── Agent Briefing Email → support team
                     │   │   Customer · intent · priority · handoff
                     │   │   summary · call ID · compliance status
                     │   │
                     │   └── Slack Alert → #insurvoice-alerts
                     │       Call ID · customer · topic · priority
                     │
                     └─ NO: (no further actions)
```

### Automation outputs

**n8n Workflow**
[![n8n Workflow](https://github.com/dbystrova26/insurvoice-ai/raw/main/screenshots/n8n_workflow_insurvoice.png)](https://github.com/dbystrova26/insurvoice-ai/blob/main/screenshots/n8n_workflow_insurvoice.png)

**Agent Briefing Email** (on escalation)
[![Agent Briefing](https://github.com/dbystrova26/insurvoice-ai/raw/main/screenshots/n8n_email_agent_briefing_escalation.png)](https://github.com/dbystrova26/insurvoice-ai/blob/main/screenshots/n8n_email_agent_briefing_escalation.png)

**Customer Summary Email** (every call)
[![Customer Email](https://github.com/dbystrova26/insurvoice-ai/raw/main/screenshots/n8n_customer_email.png)](https://github.com/dbystrova26/insurvoice-ai/blob/main/screenshots/n8n_customer_email.png)

**Slack Alert** (on escalation)
[![Slack Alert](https://github.com/dbystrova26/insurvoice-ai/raw/main/screenshots/n8n_slack_alert.png)](https://github.com/dbystrova26/insurvoice-ai/blob/main/screenshots/n8n_slack_alert.png)

---

## Voice Pipeline

```
Deepgram nova-3 WebSocket
    ↓  transcript text
InsurVoiceAgent (7-agent pipeline)
    ↓  response text
ElevenLabs TTS → MP3 bytes → base64
    ↓
Browser:
    ├── new Audio('data:audio/mpeg;base64,...').play()   ← CUSTOMER HEARS THIS
    └── decode MP3 → PCM16 → simliClient.sendAudioData() ← LIP-SYNC ONLY
         (avatarAudio element permanently muted)
```

**Key implementation details:**

- **Lip-sync timing (June 2026 fix):** PCM is decoded and sent to Simli *before* `audio.play()` starts, eliminating the 50–300ms lip lag from the original async decode
- **Mic reopening:** uses `audio.onended` event, not a timer — mic reopens exactly when Tina stops talking
- **Greeting:** fires 6 seconds after socket connect; `greeting_sent` flag prevents duplicate greetings; greeting words suppressed for 10 seconds to avoid double responses
- **STT deduplication:** Deepgram sometimes sends the same final transcript twice within 3 seconds — duplicate dropped before reaching the agent

---

## Evaluation Results (June 2026)

Tested against 30 realistic customer questions using production `agent.py` with full dual RAG active.

```
Model:   claude-sonnet-4-6
RAG:     pgvector (Supabase) + keyword fallback (knowledge_base.json)
Cases:   30
Date:    June 16, 2026
```

| Metric | Target | Result | Status |
|--------|--------|--------|--------|
| Routing accuracy | ≥ 85% | **86.7%** (26/30) | ✅ PASS |
| Keyword coverage | ≥ 70% | **85.6%** | ✅ PASS |
| Overall pass rate | — | **83.3%** | ✅ |
| Avg response time | < 8s | **4.3s** | ✅ |
| Compliance rate | 100% | **100%** | ✅ |

**Results by intent category:**

| Intent | n | Routing | KW Score | Avg Latency |
|--------|---|---------|----------|-------------|
| Billing | 5 | 100% | 87% | 4.08s |
| Claims | 5 | 60% ⚠️ | 93% | 4.85s |
| Escalation | 2 | 100% | 67% | 4.38s |
| General | 5 | 100% | 93% | 4.22s |
| Policy | 13 | 85% | 82% | 4.16s |

**Known gap:** Claims routing at 60% — implicit damage phrasing ("my pipe burst", "I broke something") routes to Policy instead of Claims. Fix: add implicit-damage keywords to Router prompt. Phase 2 priority.

---

## Knowledge Base & Policy PDFs

### Knowledge base — 87 FAQs

`mvp/web/data/knowledge_base.json`

| Category | FAQs | Key topics |
|----------|------|------------|
| home_insurance | 23 | Water/fire/theft/storm, Leitungswasser, electronics, vandalism |
| claims | 17 | Filing, timelines, rejection appeals, settlement, new-for-old |
| billing | 13 | Monthly/annual payment, grace period, surcharge, SEPA, discounts |
| policy | 13 | Renewal, cancellation, moving home, deductibles, cooling-off |
| general | 14 | Opening hours Mon-Fri 8-20 / Sat 9-17, portal, complaints, ombudsman |
| liability | 7 | Dog damage, child accidents, tenant liability, lawyer costs |

### Policy PDFs — 5 documents, 27 pgvector chunks

`mvp/web/data/policies/`

| Document | Chunks | Key content |
|----------|--------|-------------|
| Home Contents Insurance | 8 | Leitungswasser, fire, theft, sum insured, deductibles |
| Insurance Claims Guide | 5 | Filing process, timelines, documentation, settlement |
| Glass Breakage Insurance | 4 | Glasbruch extension, EUR 100 deductible |
| Extension to Home Contents Policy | 5 | Elementarschäden, flood, earthquake, natural hazards |
| Personal Liability Insurance | 5 | Haftpflicht, Tierhalterhaftpflicht, dog liability |

---

## Compliance

| Regulation | Implementation |
|------------|----------------|
| **EU AI Act Art. 52(1)** | AI identity disclosed on every first turn — enforced by ComplianceGuard in `agent.py` system prompt; cannot be skipped |
| **EU AI Act classification** | Limited Risk — screened Annex III; no binding decisions made; information-only |
| **GDPR Art. 6(1)(b)** | Legal basis: performance of contract — no consent banner required |
| **GDPR Art. 6(1)(f)** | Log data (call_id, intent, timestamp) retained 30 days under legitimate interest |
| **GDPR Art. 22** | No automated decisions — fully satisfied by design; insurer retains all decision authority |
| **GDPR Art. 17** | Right to erasure: `DELETE FROM call_log WHERE call_id = X` — one query |
| **Audio** | Streamed to Deepgram then immediately discarded — never persisted |
| **Transcripts** | Session only — not stored after response sent |
| **Log data** | call_id (UUID) · intent label · timestamp only — no message content, no audio |
| **US transfers** | Deepgram + Anthropic: Standard Contractual Clauses (Module 2) + DPAs |
| **DPIA** | Complete — residual risk: **Medium** (Deepgram audio to US). Phase 3: self-host Whisper → Low |
| **Hosting** | Render EU Frankfurt — data stays in EU except SCC-covered API calls |

---

## Deployment

### Render.com

| Setting | Value |
|---------|-------|
| Root Directory | `mvp/web` |
| Build Command | `pip install -r requirements.txt && python ../download_data.py` |
| Start Command | `gunicorn --worker-class sync --workers 1 --threads 100 --bind 0.0.0.0:$PORT --timeout 120 server:app` |

`render.yaml` location: `mvp/render.yaml` — Render reads this. `mvp/web/render.yaml` is ignored.

### Health checks

- `/api/health` — returns API key status for all services
- `/api/ping-db` — tests Supabase connection; point UptimeRobot here (5 min interval) to prevent Render sleep and Supabase auto-pause

### Environment variables

| Key | Service | Notes |
|-----|---------|-------|
| `ANTHROPIC_API_KEY` | Claude reasoning | claude-sonnet-4-6 (override with `LLM_MODEL`) |
| `LLM_MODEL` | Model selection | Default: claude-sonnet-4-6 — switch models without redeploy |
| `DEEPGRAM_API_KEY` | Live STT | nova-3 model |
| `ELEVENLABS_API_KEY` | Voice synthesis | Pay-as-you-go |
| `ELEVENLABS_VOICE_ID` | Voice ID | From ElevenLabs dashboard |
| `SIMLI_API_KEY` | Avatar lip-sync | Hobby plan after free 50 min |
| `SIMLI_FACE_ID` | Avatar face | From Simli dashboard |
| `OPENAI_API_KEY` | RAG embeddings | text-embedding-3-large for pgvector ingestion |
| `DATABASE_URL` | Supabase PostgreSQL | Session Pooler URL (port 5432, IPv4) |
| `FLASK_SECRET` | Session security | Any random string |
| `N8N_WEBHOOK_URL` | Automation | Webhook URL for call logging and escalation |

**Supabase connection:** Use the **Session Pooler** URL from Supabase → Connect → Session pooler (port 5432). Direct connection and Transaction pooler have IPv6 issues on Render free tier.

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

↗️  EscalationManager fires → n8n Automation:
   ├── 📊 Google Sheets: call logged (call_id, intent, summary, timestamp)
   ├── 📧 Agent Briefing: email sent to CS team with handoff summary
   ├── 📧 Customer Summary: email sent to customer with conversation recap
   └── 💬 Slack Alert: posted to #insurvoice-alerts
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
        ├── agent.py             ← InsurVoiceAgent — 7-agent pipeline orchestration
        ├── rag.py               ← Dual retrieval: pgvector + keyword + circuit breaker
        ├── knowledge.py         ← 87-FAQ keyword search (KnowledgeBase agent)
        ├── stream.py            ← DeepgramStreamSession (WebSocket STT)
        ├── voice.py             ← ElevenLabs MP3 synthesis
        ├── crm.py               ← Supabase CRM lookup + call_log (retry thread)
        ├── n8n_integration.py   ← EscalationManager: webhook, urgency, summaries
        ├── evaluate.py          ← 30-question accuracy evaluation suite
        ├── requirements.txt
        ├── data/
        │   ├── knowledge_base.json   ← 87 FAQs (KnowledgeBase agent)
        │   └── policies/             ← 5 policy PDFs (PolicyRAG agent)
        ├── static/
        │   ├── avatar.js
        │   └── simli-client.js
        └── templates/
            ├── index.html            ← Voice-only interface
            └── avatar.html           ← Tina avatar with lip-sync
```

---

## What's Working (June 2026)

| Feature | Status |
|---------|--------|
| Avatar loads + lip-syncs (fixed 50–300ms lag) | ✅ |
| Single greeting per session | ✅ |
| No duplicate STT responses (3s debounce) | ✅ |
| Live mic transcription (Deepgram nova-3) | ✅ |
| Mic reopens via audio.onended (not timer) | ✅ |
| Claude Sonnet 4.6 response generation | ✅ |
| Dynamic model via LLM_MODEL env var | ✅ |
| ElevenLabs voice synthesis (MP3) | ✅ |
| Dual RAG: pgvector + FAQ keyword | ✅ |
| RAG circuit breaker (graceful fallback) | ✅ |
| 87-FAQ knowledge base preserved across deploys | ✅ |
| Intent routing (claims/billing/policy/general/escalation) | ✅ |
| EU AI Act Art. 52 disclosure on first turn | ✅ |
| CRM lookup by name + policy number | ✅ |
| call_log written to Supabase (retry thread, 20 attempts) | ✅ |
| n8n webhook fires on call end | ✅ |
| Google Sheets logging | ✅ |
| Gmail notifications (agent briefing + customer summary) | ✅ |
| Slack escalation alerts | ✅ |
| /api/health + /api/ping-db | ✅ |

---

## Author

**Daria Bystrova** · Ironhack AI Consulting & Integration Bootcamp · Berlin 2026  
GitHub: [github.com/dbystrova26](https://github.com/dbystrova26) · Project: [github.com/dbystrova26/insurvoice-ai](https://github.com/dbystrova26/insurvoice-ai)  
Live: [insurvoice-ai.onrender.com/avatar](https://insurvoice-ai.onrender.com/avatar)

*Fictional scenario for educational purposes. Not affiliated with Allianz, Anthropic, Deepgram, ElevenLabs, Simli, Supabase, or n8n.*
