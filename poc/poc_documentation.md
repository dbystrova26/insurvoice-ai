# POC Documentation — InsurVoice AI

**File:** `poc/poc_documentation.md`
**POC type:** No-code webhook prototype
**Stack:** n8n (full orchestration) + Deepgram (STT) + Claude (reasoning) + ElevenLabs (TTS)
**Author:** Daria Bystrova | Ironhack AI Consulting Bootcamp | June 2025

---

## What the POC Is

The POC is a working voice agent built entirely inside n8n — no Python, no database, no deployment. Its only job was to answer one question: **can an AI voice agent handle insurance customer queries end-to-end?**

It answered yes. That validated the idea and unlocked the MVP build.

---

## What the POC Actually Does

A customer query arrives at an n8n webhook as a JSON transcript. n8n loads a small set of insurance FAQs, builds a prompt, calls Claude, parses the response, and returns a JSON reply. If the query requires escalation, n8n generates a handoff summary and logs the call to Google Sheets.

```
Webhook receives:
  { transcript, conversation_id, turn_number, history }
        ↓
Load 7 core insurance FAQs (inline in workflow)
        ↓
Build Claude prompt:
  - EU AI Act Art. 52 disclosure on turn 1
  - FAQ context
  - Conversation history
  - Intent classification instruction
        ↓
Call Claude API
        ↓
Parse JSON response:
  { intent, confidence, response, should_escalate, escalation_reason }
        ↓
Route:
  - Not escalated → return { response, intent }
  - Escalated → generate handoff summary → return escalation response
        ↓
Log to Google Sheets (every turn, anonymised)
```

The transcript is provided externally — the POC does not handle audio capture or live streaming. That was a deliberate simplification to test the reasoning loop first.

---

## What the POC Proved

Five things that were genuinely unknown before building it:

1. **Intent classification works** — Claude reliably distinguishes claims, billing, policy, and escalation queries from real insurance questions, using only a prompt
2. **EU AI Act Art. 52 enforcement is prompt-achievable** — AI disclosure on first turn can be enforced via system prompt alone without a dedicated compliance layer
3. **Escalation detection works** — Claude correctly identifies when a query needs a human and generates a useful handoff summary
4. **The core loop is fast enough** — n8n webhook → Claude → response in under 4 seconds, well within conversational tolerance
5. **Google Sheets logging works** — every call can be captured for audit without a database

These five validations gave enough confidence to build the MVP.

---

## POC vs MVP — What Changed and Why

The POC left out everything that was not needed to validate the core idea. The MVP adds everything required for a real product.

| Feature | POC | MVP | Why it changed |
|---|---|---|---|
| **Agent logic** | Single Claude prompt inside n8n | Python multi-agent: Router + 4 Specialists + Escalation + ComplianceGuard | One prompt cannot be maintained or tested reliably at scale |
| **n8n role** | Core orchestrator: webhook → Claude → response | Post-call automation only: Gmail + Google Sheets + Slack after Python finishes | Python is better suited for stateful multi-turn agent logic |
| **FAQ knowledge** | 7 FAQs hardcoded inside n8n workflow | 154 FAQs from 5 real policy PDFs, embedded in pgvector (Supabase) | 7 FAQs do not cover real customer questions; keyword search misses paraphrases |
| **RAG** | None — FAQs inline in prompt | Semantic search via pgvector (`rag.py`), keyword fallback via `knowledge.py` | Vector embeddings find relevant content even when exact words don't match |
| **CRM** | None | Supabase PostgreSQL — `customers`, `claims`, `call_log` tables | Agents need to know who they're talking to and personalise responses |
| **Compliance** | Prompt instruction only | Dedicated `ComplianceGuard` agent with deterministic regex + LLM rewrite | A prompt instruction can be overridden by a clever query; a dedicated agent cannot |
| **Audio / STT** | External — transcript provided to webhook | Live Deepgram nova-3 WebSocket streaming inside Flask + SocketIO | Real customers speak live; they cannot submit a pre-transcribed file |
| **Interface** | Webhook API (JSON in / JSON out) | Browser with live microphone, Simli lip-synced avatar, agent trace panel | Stakeholders and real customers need a UI |
| **Language** | English only | langdetect auto-detects EN / DE / ES / FR / IT; replies in detected language | Allianz Direct serves a multilingual European market |
| **Call logging** | Google Sheets via n8n | Supabase `call_log` table (direct, every turn) + Google Sheets via n8n | Database gives queryable analytics; Sheets gives human-readable audit |
| **Deployment** | Local n8n only | Render.com (Flask) + Supabase Cloud + n8n Cloud | POC cannot be shown to external stakeholders or tested by others |

---

## How n8n's Role Changed

In the **POC**, n8n was the brain. It handled the entire customer interaction from receiving the transcript to calling Claude to returning the response.

In the **MVP**, Python took over as the brain. The multi-agent pipeline (`orchestrator.py` → `router.py` → `specialists.py` → `compliance_guard.py`) handles all conversation logic. n8n now fires only once, after Python has finished a turn, to handle post-call automation: logging to Google Sheets, emailing the customer a summary, emailing the agent a briefing if escalated, and posting to Slack.

n8n is present in both phases — doing completely different jobs.

---

## Tools Used

| Tool | POC role | MVP role |
|---|---|---|
| **n8n** | Core orchestrator — entire conversation flow | Post-call automation — Gmail + Google Sheets + Slack |
| **Claude** | Intent classification + response generation (via n8n HTTP node) | Same, but called by Python multi-agent pipeline |
| **Deepgram** | Not in POC — transcript provided externally | Live WebSocket STT (`stream.py`) |
| **ElevenLabs** | TTS via n8n HTTP node | TTS via Python `voice.py` |
| **Google Sheets** | Call log | Call log (same) |
| **Gmail** | Not in POC | Customer summary + agent briefing via n8n |
| **Slack** | Not in POC | Escalation alerts to #insurvoice-alerts via n8n |
| **Supabase** | Not in POC | CRM (`customers`, `claims`) + `call_log` (PostgreSQL + pgvector) |
| **pgvector** | Not in POC | Semantic search over 5 policy PDFs (`rag.py`) |
| **Simli** | Not in POC | Lip-synced avatar (WebRTC) |
| **Flask + SocketIO** | Not in POC | Web interface with live browser microphone |

---

## Reproducing the POC

**Prerequisites:**
- n8n account (free at n8n.cloud, or run locally: `npx n8n`)
- `ANTHROPIC_API_KEY`
- Optionally: Google Sheets credential for logging

**Steps:**

1. Import `poc/poc_workflow.json` into n8n
2. In the **Call Claude API** node → Credentials → Header Auth → name: `x-api-key`, value: your Anthropic key
3. Toggle workflow **Active** → copy the webhook URL
4. Send a test call:

```bash
curl -X POST https://YOUR-WEBHOOK-URL \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Does my home insurance cover a burst pipe?",
    "conversation_id": "test-001",
    "turn_number": 1,
    "history": []
  }'
```

5. Expected response:

```json
{
  "response": "Hello, I am Tina, an AI assistant for Allianz Direct — not a human. Burst pipe water damage is covered under your Hausratversicherung as Leitungswasser damage. Your EUR 250 deductible applies. Is this about an active incident?",
  "intent": "policy_coverage",
  "escalated": false
}
```

**To run the MVP instead:**

```bash
cd mvp/web
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
python server.py
# Open http://localhost:5000/avatar
```

---

## POC Workflow — File Reference

`poc/poc_workflow.json` — importable n8n workflow, 8.7 KB

Nodes:
- **Webhook** — receives transcript + conversation context
- **Load KB** — 7 inline insurance FAQs
- **Build Prompt** — assembles system prompt with FAQs, history, EU AI Act instruction
- **Call Claude API** — HTTP request to Anthropic API
- **Parse Response** — extracts intent, response, escalation flag
- **Route** — branches on `should_escalate`
- **Return Response** — sends JSON back to caller
- **Log to Sheets** — appends anonymised row to Google Sheets audit log
