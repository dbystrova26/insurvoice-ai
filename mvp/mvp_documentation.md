# MVP Documentation — InsurVoice AI

*Ironhack AI Consulting & Integration Bootcamp · Final Project · `mvp/mvp_documentation.md`*

> The working, deployed application. **Source + commit history:** <https://github.com/dbystrova26/insurvoice-ai> · **Live:** <https://insurvoice-ai.onrender.com/avatar>

---

## 1. Architecture Overview

```
                    ┌────────────────────── Render.com EU (Frankfurt) ──────────────────────┐
Customer speaks ──► │  Deepgram nova-3 (WebSocket STT)                                      │
 or types           │       │                                                               │
                    │       ▼                                                               │
                    │  server.py (Flask + SocketIO)                                         │
                    │       │                                                               │
                    │       ▼                                                               │
                    │  agent.py ── 7-AGENT PIPELINE:                                       │
                    │       ├── Router          (intent: claims/policy/billing/general/     │
                    │       │                    escalation)                                │
                    │       ├── KnowledgeBase   (87-FAQ keyword search → knowledge.py)     │
                    │       ├── PolicyRAG       (pgvector cosine similarity → rag.py)      │
                    │       ├── CRM             (Supabase customer lookup → crm.py)        │
                    │       ├── ResponseGenerator (Claude Sonnet 4.6 API call)             │
                    │       ├── ComplianceGuard  (EU AI Act Art. 52 + no-decisions check)  │
                    │       └── EscalationManager (n8n webhook → n8n_integration.py)       │
                    │       │                                                               │
                    │       ▼                                                               │
                    │  voice.py ── ElevenLabs TTS ── MP3 → browser                        │
                    │       │                                                               │
                    │       ├── audio.play() ──────────────────── customer hears Tina      │
                    │       └── PCM decode → Simli WebRTC ──────── lip-sync only           │
                    │                                                                       │
                    │  Supabase (PostgreSQL + pgvector):                                   │
                    │       ├── policy_chunks   (27 PDF chunks, vector(1536))              │
                    │       ├── customers       (20 mock CRM records)                      │
                    │       └── call_log        (audit trail, no PII, GDPR Art. 30)        │
                    └───────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    n8n Webhook (on call end):
                         ├── Google Sheets log (ALL calls)
                         ├── Customer summary email (ALL calls)
                         ├── Agent briefing email (escalations only)
                         └── Slack alert → #insurvoice-alerts (escalations only)
```

**Layers:** Live WebSocket STT (Deepgram) feeds a 7-agent Claude pipeline backed by Dual RAG — a keyword FAQ layer and pgvector semantic search over real policy PDFs. Responses are synthesised to speech (ElevenLabs) and lip-synced to an avatar (Simli). Every call is logged to Supabase and triggers an n8n automation webhook. One Flask + SocketIO server serves both the API and the avatar frontend.

---

## 2. Setup & Installation

**Prerequisites:** Python 3.11+, API keys for Anthropic, Deepgram, ElevenLabs, Simli, OpenAI (RAG embeddings only), Supabase, and n8n.

```bash
git clone https://github.com/dbystrova26/insurvoice-ai
cd insurvoice-ai/mvp/web
pip install -r requirements.txt
cp .env.example .env        # fill in your keys — never commit .env
python rag.py --ingest      # embed policy PDFs → Supabase (run once)
```

**Environment variables**

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | ✅ | Claude Sonnet 4.6 — response generation |
| `LLM_MODEL` | optional | Default `claude-sonnet-4-6` — swap model without redeploy |
| `DEEPGRAM_API_KEY` | ✅ | Live WebSocket speech-to-text (nova-3) |
| `ELEVENLABS_API_KEY` | ✅ | Text-to-speech voice synthesis |
| `ELEVENLABS_VOICE_ID` | ✅ | Tina's voice ID from ElevenLabs dashboard |
| `SIMLI_API_KEY` | ✅ | Lip-sync avatar (WebRTC) |
| `SIMLI_FACE_ID` | ✅ | Avatar face ID from Simli dashboard |
| `OPENAI_API_KEY` | ✅ | `text-embedding-3-large` for PDF ingestion only |
| `DATABASE_URL` | ✅ | Supabase Session Pooler URL (port 5432, IPv4) |
| `FLASK_SECRET` | ✅ | Session security — any random string |
| `N8N_WEBHOOK_URL` | ✅ | n8n call-end webhook for logging + escalation |

> **Supabase connection:** use the **Session Pooler** URL from Supabase → Connect (port 5432). Direct and Transaction Pooler connections have IPv6 issues on Render free tier.

---

## 3. How to Run It

**Locally:**

```bash
cd mvp/web
python server.py
# open http://localhost:5000/avatar
```

**On Render.com:**

New web service from the repo. Set root directory to `mvp/web`, build command to `pip install -r requirements.txt && python ../download_data.py`, start command to:

```
gunicorn --worker-class sync --workers 1 --threads 100 --bind 0.0.0.0:$PORT --timeout 120 server:app
```

Set all environment variables above. The avatar interface is served at `/avatar`.

**Health checks:**

- `/api/health` — returns API key status for all services
- `/api/ping-db` — tests Supabase connection; point UptimeRobot here (5 min interval) to prevent Render free-tier sleep and Supabase auto-pause

**Walk-through:** Open `/avatar` → Tina greets you automatically after 6 seconds → speak naturally or use the text input → ask about your policy ("My pipe burst, am I covered?") → ask a billing question ("Can I pay monthly?") → say "I want to speak to a human" to trigger the escalation automation and see n8n fire.

---

## 4. Basic Error Handling (Fails Gracefully)

- **RAG circuit breaker:** if Supabase is unreachable, the pipeline falls back to keyword-only FAQ retrieval automatically — the voice agent keeps responding without crashing.
- **call_log retries:** Supabase writes are retried in a background thread (20 attempts, exponential backoff) so a brief DB hiccup never blocks the voice response.
- **n8n webhook:** fires in a background thread — automation failure does not affect the customer-facing call in any way.
- **STT deduplication:** Deepgram sometimes sends the same final transcript twice within 3 seconds; the duplicate is dropped before reaching the agent pipeline.
- **Greeting deduplication:** a `greeting_sent` flag prevents duplicate greetings per session; greeting trigger words are suppressed for 10 seconds after connect.
- **Lip-sync timing:** PCM is decoded and sent to Simli before `audio.play()` starts, avoiding the 50–300ms lip lag that occurred in earlier versions when decode was async.
- **Microphone timing:** mic re-opens via `audio.onended` event, not a timer — Tina cannot hear the customer while she is still speaking.

---

## 5. Known Limitations & What Production Would Need

| Area | POC today | Production |
|------|-----------|------------|
| Telephony | Browser microphone only | Twilio SIP trunk — customers dial existing number, no app needed |
| CRM | 20 mock customers, name + policy lookup | Live policy system REST API, PIN + date-of-birth identity verification |
| Knowledge base | 87 synthetic FAQs + 5 sample PDFs | Insurer's real documentation, full policy library, auto-refresh on update |
| Authentication | None | PIN verification before disclosing any account-level information |
| Infrastructure | Render free tier, cold starts ~30s | Dedicated instance, 99.9% SLA, auto-scaling |
| Routing accuracy | 83–87% (30-case eval) — claims intent weak at 60% | ≥95% with domain-specific fine-tuning and implicit-damage keyword expansion |
| Analytics | Google Sheets + Supabase call_log | Live Grafana / Looker Studio dashboard with deflection rate, CSAT, latency |
| Languages | EN + DE auto-detect | Localised knowledge base per market, ElevenLabs voice clone per language |
| STT privacy | Deepgram audio transfer to US (SCCs + DPA mitigated) | Self-hosted Whisper in EU — eliminates US audio transfer, DPIA risk: Low |
| Tenancy | Single insurer instance | Multi-tenant SaaS — white-label Tina persona per client |

---

## 6. How It Extends the POC

A bare proof of concept would only demonstrate "an LLM can answer insurance questions." This build goes well beyond that, into a deployable, evaluated, compliant voice agent:

- **From chatbot → voice agent with a face:** Deepgram live STT, ElevenLabs TTS, and Simli WebRTC lip-sync turn a text Q&A system into a real-time phone-style interaction with a visible AI persona. Customers see and hear Tina, not a chat bubble.

- **From single prompt → 7-agent pipeline:** routing, retrieval, CRM lookup, generation, compliance review, and escalation are separated into independent agents. Each has one job, one failure mode, and is independently testable. The eval suite measures routing accuracy, keyword coverage, and compliance rate as separate metrics.

- **From keyword search → Dual RAG:** a 87-FAQ keyword layer (fast, deterministic, zero cost) runs in parallel with pgvector semantic search over 5 real policy PDFs. Neither layer alone gives full coverage — keyword misses implicit phrasing; pgvector handles it semantically. Both merge before Claude generates a response.

- **From no data layer → Supabase serving three jobs:** pgvector embeddings for semantic retrieval, CRM mock data for personalised responses, and a GDPR-compliant `call_log` audit trail — all in one Postgres instance.

- **From manual → automated escalation via n8n:** when the agent cannot resolve a query, EscalationManager fires an n8n webhook that simultaneously logs to Google Sheets, emails a handoff briefing to the CS agent, emails a summary to the customer, and posts a Slack alert. Zero manual steps.

- **From demo → evaluated:** 30 test cases with ground-truth expected routes run against the production pipeline. Results: 86.7% routing accuracy (target ≥85% ✅), 100% compliance rate ✅, 4.3s avg response time ✅. The one weak spot (claims routing at 60%) is documented with a root cause and fix.

- **From unregulated → compliant by design:** EU AI Act Art. 52(1) disclosure fires on every first turn (enforced by ComplianceGuard at runtime, not just in documentation). No automated decisions are ever made. Audio is discarded immediately after transcription. DPIA complete — residual risk: Medium.

In short: the POC proves the **capability**; this build proves the **pipeline architecture, the retrieval accuracy, the automation, and the regulatory deployability** around it.

---

*Daria Bystrova · Ironhack AI Consulting & Integration Bootcamp · Berlin 2026*  
*Fictional scenario for educational purposes. Not affiliated with Allianz, Anthropic, Deepgram, ElevenLabs, Simli, Supabase, or n8n.*
