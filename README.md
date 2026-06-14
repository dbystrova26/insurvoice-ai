# InsurVoice AI

![InsurVoice AI Banner](banner.png)

**AI voice agent for insurance customer service — meet Tina.**
Ironhack AI Consulting Bootcamp · Final Project · Daria Bystrova

AI voice agent for insurance customer service built as an Ironhack AI Consulting Capstone Project. Speak naturally in any language and Tina, a lip-synced avatar, hears you via live speech recognition (Deepgram), reasons through a multi-agent pipeline (Claude), retrieves answers from a 154-FAQ knowledge base, looks up your policy from a CRM database (Supabase), and speaks back in your language (ElevenLabs). Every escalation automatically triggers an n8n workflow — Gmail briefing, Google Sheets log, and a Slack alert. EU AI Act Article 52 and GDPR compliant by design.

---

## Live Demo

🚀 **[Launch Voice Interface](https://insurvoice-ai.onrender.com)** — voice only  
🎭 **[Launch Avatar Interface](https://insurvoice-ai.onrender.com/avatar)** — Tina with lip-sync  

*First load ~30s on free Render tier.*

---

## Architecture

![System Architecture](architecture.png)

> **Full diagram:** [architecture.png](architecture.png) — shows the complete pipeline including Supabase CRM and n8n automation layer.

### Voice Pipeline

```
You speak / type
    ↓
Deepgram nova-3 ── live streaming STT, accent-robust, no button press
    ↓
langdetect ──────── auto-detects EN / DE / ES / FR / IT from transcript
    ↓
Supabase CRM ────── looks up customer by name + policy number (PostgreSQL)
    ↓
Tina Orchestrator ─ greeting → language select → CRM → route → specialist
    │
    ├── Router agent ────────── classifies intent
    ├── Claims specialist ───── filing, status, documents
    ├── Billing specialist ───── premiums, payments, invoices
    ├── Policy specialist ────── coverage, renewals, cancellations
    ├── General specialist ───── hours, contacts, portal
    ├── Escalation agent ─────── human handoff + written briefing
    └── Compliance Guard ─────── EU AI Act Art. 52 + GDPR check
    ↓
ElevenLabs TTS ──── text → spoken voice in detected language
    ↓
Simli WebRTC ────── lip-synced avatar face (optional)
    ↓
You hear + see Tina's answer
```

### Automation Layer (fires after every turn)

```
Tina Orchestrator
    ↓ (n8n webhook, non-blocking background thread)
n8n Workflow
    ├── Google Sheets ── logs every call (intent, route, language, escalated, summary)
    ├── Gmail ────────── sends HTML call summary to customer
    ├── Gmail ────────── if escalated: sends full agent briefing
    ├── Slack ────────── if escalated: posts to #insurvoice-alerts with urgency
    └── Supabase ─────── call_log table updated (PostgreSQL)
```

---

## Meet Tina

Tina is InsurVoice AI's persona — a professional, multilingual insurance assistant powered by Claude. On every new call:

1. **Tina greets you** — *"Hi, I'm Tina from Allianz Direct. English or Deutsch?"*
2. **You choose your language** — Tina switches immediately
3. **Tina asks for your details** — *"Could you give me your name and policy number?"*
4. **Tina pulls your account from Supabase** — *"Hello Anna! Your policy POL-4821 is active. Your claim CLM-2847 is under assessment..."*
5. **Natural conversation continues** — any insurance topic, in your language

---

## Multi-Agent Architecture

Seven agents working in coordination:

| Agent | What it does |
|---|---|
| **Router** | Classifies intent, delegates to the right specialist |
| **Claims specialist** | Filing claims, status, documents, timelines |
| **Billing specialist** | Premiums, payments, invoices, refunds |
| **Policy specialist** | Coverage, renewals, cancellations, changes |
| **General specialist** | Hours, contacts, portal, complaints |
| **Escalation agent** | Human handoff script + written briefing for receiving agent |
| **Compliance Guard** | Checks every reply — EU AI Act Art. 52 + GDPR — before it is spoken |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Speech-to-text** | Deepgram nova-3 (live WebSocket streaming) |
| **Language detection** | langdetect (Python, no API needed) |
| **Reasoning** | Anthropic Claude claude-opus-4-6 |
| **Text-to-speech** | ElevenLabs eleven_turbo_v2_5 (multilingual) |
| **Avatar** | Simli WebRTC (lip-synced, LiveKit transport) |
| **Knowledge base** | 154-FAQ keyword RAG |
| **CRM database** | Supabase (PostgreSQL, free hosted) |
| **Automation** | n8n (Gmail + Google Sheets + Slack) |
| **Web interface** | Flask + SocketIO |
| **Compliance** | EU AI Act Art. 52 + GDPR enforced at runtime |
| **Deployment** | Render.com |

---

## Project Structure

```
insurvoice-ai/
├── banner.png
├── architecture.png
├── README.md
├── STORY.md
├── use_case_definition.md
├── roi_risk_assessment.md
├── strategic_plan.md
├── compliance/
│   ├── eu_ai_act_compliance.md
│   └── gdpr_documentation.md
├── poc/
│   ├── poc_workflow.json
│   └── poc_documentation.md
└── mvp/
    ├── agents/
    │   ├── orchestrator.py        # Tina flow: greeting → language → CRM → pipeline
    │   ├── router.py              # intent classification
    │   ├── specialists.py         # claims / billing / policy / general
    │   ├── escalation.py          # human handoff + briefing
    │   ├── compliance_guard.py    # EU AI Act + GDPR checker
    │   └── ARCHITECTURE.md
    └── web/                       # Flask voice interface ⭐
        ├── server.py              # Flask + SocketIO, all keys server-side
        ├── stream.py              # Deepgram nova-3 live WebSocket STT
        ├── crm.py                 # Supabase CRM lookup
        ├── n8n_integration.py     # n8n webhook trigger
        ├── knowledge.py           # RAG retrieval
        ├── evaluate.py            # 30-question accuracy evaluation
        ├── supabase_schema.sql    # database schema + mock data
        ├── insurvoice_n8n_workflow.json  # importable n8n workflow
        ├── agents/                # agent package (mirrored for Render)
        ├── data/
        │   └── knowledge_base.json  # 154 insurance FAQs
        ├── static/
        │   └── simli-client.js    # Simli WebRTC SDK (bundled)
        ├── templates/
        │   ├── index.html         # voice-only interface
        │   └── avatar.html        # Tina avatar interface
        ├── requirements.txt
        └── render.yaml
```

---

## Quick Start

```bash
git clone https://github.com/dbystrova26/insurvoice-ai.git
cd insurvoice-ai/mvp/web

pip install -r requirements.txt
pip install psycopg2-binary langdetect

cp .env.example .env   # fill in your API keys (see below)
python server.py
```

Open **http://localhost:5000/avatar** — Tina greets you automatically.

---

## Required API Keys

All free tiers are sufficient for development and demo:

| Key | Service | Free tier | Get it at |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Claude reasoning | $5 free credit | console.anthropic.com |
| `DEEPGRAM_API_KEY` | Live speech-to-text | 12,000 min/month | console.deepgram.com |
| `ELEVENLABS_API_KEY` | Voice synthesis | 10,000 chars/month | elevenlabs.io |
| `ELEVENLABS_VOICE_ID` | Your voice ID | — | ElevenLabs dashboard |
| `SIMLI_API_KEY` | Avatar lip-sync | 200 min/month | simli.com |
| `SIMLI_FACE_ID` | Avatar face | — | Simli dashboard |
| `DATABASE_URL` | Supabase PostgreSQL | Free forever | supabase.com |
| `N8N_WEBHOOK_URL` | Automation | Free trial | n8n.io |

---

## Supabase CRM Setup

InsurVoice uses **Supabase** (free hosted PostgreSQL) as its mock CRM. When a customer gives their name and policy number, Tina queries the database and personalises the response.

### Setup steps

**1. Create a Supabase project**
- Go to [supabase.com](https://supabase.com) → New project → name it `insurvoice-ai`
- Region: West EU (Frankfurt or Paris)
- Save your database password

**2. Run the schema**
- Supabase dashboard → **SQL Editor** → **New query**
- Paste contents of `mvp/web/supabase_schema.sql`
- Click **Run** — creates 3 tables + 20 mock customers + 10 claims

**3. Disable RLS** (for server-side access)
```sql
ALTER TABLE customers DISABLE ROW LEVEL SECURITY;
ALTER TABLE claims DISABLE ROW LEVEL SECURITY;
ALTER TABLE call_log DISABLE ROW LEVEL SECURITY;
```

**4. Get your connection string**
- Settings → Database → Connection string → URI
- Looks like: `postgresql://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres`

**5. Add to `.env`**
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.xxxx.supabase.co:5432/postgres
```

### Database schema

```
customers    — 20 mock policyholders (name, email, policy number, premium, next payment)
claims       — 10 mock claims linked to customers (status, amount, expected decision)
call_log     — every InsurVoice call logged automatically
```

### Test customers for demo

| Name | Policy | Type | Language |
|---|---|---|---|
| Anna Müller | POL-4821 | Home Contents + Liability | DE |
| Thomas Weber | POL-3392 | Home Contents + Glass | DE |
| James Wilson | POL-7701 | Home Contents + Liability | EN |
| Carlos García | POL-9923 | Home Contents | ES |
| Marie Dupont | POL-1045 | Home Contents + Liability | FR |

---

## n8n Automation Setup

Every InsurVoice call automatically triggers an **n8n workflow** that:
- Logs the call to Google Sheets
- Sends the customer an email summary
- If escalated: emails the human agent a full briefing + sends a Slack alert

### Setup steps

**1. Sign up at [n8n.io](https://n8n.io)** — free trial, no credit card

**2. Import the workflow**
- n8n dashboard → Workflows → Import from file
- Upload `mvp/web/insurvoice_n8n_workflow.json`

**3. Connect credentials** (click each node → Credentials):
- Google Sheets → sign in with Google
- Gmail (×2) → sign in with Gmail
- Slack → connect your Slack workspace + add bot to `#insurvoice-alerts` channel

**4. Set up Google Sheets**
- Create a sheet named `invoice-ai-data-log`
- Add a tab called `call_log`
- Add headers in Row 1: `Timestamp | Call ID | Customer Name | Customer Email | Language | Intent | Route | Escalated | Resolved | Turns | Duration (s) | Compliance | Summary`
- Paste your Sheet URL into the Google Sheets node

**5. Get your webhook URL**
- Click the **Call Ended Webhook** node → Production URL tab
- Copy: `https://yourname.app.n8n.cloud/webhook/insurvoice-call`

**6. Add to `.env`**
```
N8N_WEBHOOK_URL=https://yourname.app.n8n.cloud/webhook/insurvoice-call
```

**7. Publish the workflow** — toggle Active in n8n top right

### What gets sent to n8n after each call

```json
{
  "call_id": "abc123-1234567890",
  "timestamp": "2025-06-14 10:30",
  "customer_name": "Anna Müller",
  "customer_email": "anna@gmail.com",
  "intent": "file_claim",
  "route": "claims",
  "language": "de",
  "escalated": false,
  "resolved": true,
  "turn_count": 3,
  "urgency": "medium",
  "summary": "Customer contacted about filing a water damage claim.",
  "compliance_passed": true
}
```

---

## Evaluation

Run the automated accuracy evaluation:

```bash
cd mvp/web
python evaluate.py
```

Tests 30 realistic customer questions. Scores:

| Metric | Target | Result |
|---|---|---|
| Routing accuracy | ≥ 85% | 83% (improving) |
| Keyword coverage | ≥ 70% | 78% ✅ |
| Compliance rate | 100% | 100% ✅ |
| Avg response time | < 8s | 6.3s ✅ |

Results saved to `eval_results.json`.

---

## Deploy to Render

**1.** Push to GitHub  
**2.** Render → New → Web Service → connect repo  
**3.** Root Directory: `mvp/web`  
**4.** Add environment variables (all 8 API keys)  
**5.** Render reads `render.yaml` — auto-configures gunicorn + eventlet  

Supabase and n8n run on their own clouds — only Flask runs on Render.

---

## Demo Script

Use these phrases to showcase every feature:

**Language + CRM lookup:**
> *"English"* → *"Anna Müller, POL-4821"*
> Tina finds Anna's account and personalises the greeting

**Claims:**
> *"How do I file a claim?"* → routes to Claims specialist

**Compliance Guard:**
> *"Are you a real person?"* → Tina must identify as AI (EU AI Act Art. 52)

**German conversation:**
> *"Wie melde ich einen Schaden?"* → langdetect → German reply

**Escalation + n8n:**
> *"I want to speak to a human"* → escalation → Slack alert + email fires automatically

---

## Compliance

| Regulation | Implementation |
|---|---|
| EU AI Act Art. 52 | AI identity disclosed on first turn; ComplianceGuard enforces at runtime |
| GDPR | Audio streamed then discarded; not stored; no biometric profiling |
| Data minimisation | Only intent labels logged, not message content |

---

## Author

**Daria Bystrova** · Ironhack AI Consulting Bootcamp · 2025  
GitHub: [github.com/dbystrova26/insurvoice-ai](https://github.com/dbystrova26/insurvoice-ai)

*Fictional scenario for educational purposes. Not affiliated with Allianz, Anthropic, Deepgram, ElevenLabs, Simli, Supabase, or n8n.*
