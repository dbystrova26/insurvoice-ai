# POC Documentation — InsurVoice AI

**File:** `poc/poc_documentation.md`  
**POC type:** No-code / low-code voice agent prototype  
**Stack:** n8n (full orchestration) + Deepgram REST (batch STT) + Claude (reasoning) + ElevenLabs (TTS)

---

## POC vs MVP — What Changed and Why

The POC and MVP are two stages of the same product. The POC validated the core idea. The MVP built it properly.

### What POC and MVP mean here

**POC** — a quick prototype to answer: *can we build a working voice loop at all?*  
Built in a weekend using n8n as the brain — no Python, no agents, no database.

**MVP** — the full product built after the POC proved the concept works.  
Python multi-agent system, live streaming STT, CRM, avatar, automation.

### How n8n's role changed

In the **POC**, n8n was the core orchestrator — it handled the entire flow from receiving the transcript to calling Claude to returning the response. It was the brain.

In the **MVP**, Python took over as the brain (multi-agent pipeline). n8n stayed in the project but shifted to a different role — it now handles **post-call automation** (logging, emails, Slack alerts) after Python finishes the conversation.

So n8n is present in both phases — just doing different jobs.

---

## POC vs MVP Feature Comparison

| Feature | POC | MVP |
|---|---|---|
| **STT** | Deepgram REST — batch transcription after recording | Deepgram nova-3 WebSocket — live streaming, no button press |
| **Agent logic** | Single Claude call via n8n | Python multi-agent: Router + 4 Specialists + Escalation + ComplianceGuard |
| **n8n role** | Core orchestrator: STT → Claude → response | Automation layer: Gmail + Google Sheets + Slack after each call |
| **Compliance** | Prompt instruction ("identify as AI on turn 1") | ComplianceGuard agent — deterministic regex + LLM rewrite if triggered |
| **CRM** | None | Supabase PostgreSQL — 20 mock customers + 10 claims |
| **Avatar** | None | Simli WebRTC — lip-synced animated face |
| **Language** | English only | Auto-detect EN/DE/ES/FR/IT via langdetect |
| **Interface** | API only (JSON in/out) | Voice + Avatar (Flask + SocketIO + browser mic) |
| **Deployment** | Local n8n only | Render.com + Supabase Cloud + n8n Cloud |

---

## What the POC Validated

One question: **does the voice loop work end-to-end?**

```
Caller speaks
    ↓
Deepgram REST → text transcript
    ↓
n8n: load KB → build Claude prompt → call Claude API
    ↓
Claude: classify intent + generate response
    ↓
n8n: parse response → route (normal or escalate)
    ↓
ElevenLabs: text → speech
    ↓
Caller hears the answer
```

The POC proved:
- Deepgram accurately transcribes insurance queries including non-native accents
- Claude reliably classifies insurance intents and generates appropriate responses
- ElevenLabs produces natural-sounding voice replies in under 3 seconds
- EU AI Act Art. 52 AI disclosure can be enforced on the first turn via prompt
- Escalation detection works — Claude correctly identifies when to hand off

---

## POC n8n Workflow — Step by Step

The `poc_workflow.json` contains the full POC orchestration:

```
1. Webhook receives: {transcript, conversation_id, turn_number, history}
       ↓
2. Load KB — 7 core insurance FAQs inline
       ↓
3. Build Claude prompt:
       - EU AI Act disclosure on turn 1
       - KB context
       - Conversation history
       - Intent classification instruction
       ↓
4. Call Claude API → returns JSON:
       {intent, confidence, response, should_escalate, escalation_reason}
       ↓
5. Parse response
       ↓
6a. Not escalated → return {response, intent} to caller
6b. Escalated → generate handoff summary → return escalation response
       ↓
7. Log to Google Sheets (every turn, anonymised)
```

---

## MVP n8n Workflow — What It Does Now

In the MVP, n8n no longer orchestrates the conversation. Python does that. n8n fires after each turn as an automation trigger:

```
Python (Flask) handles the full conversation turn
    ↓ (background thread, non-blocking)
n8n webhook receives call data
    ↓
Always: Log to Google Sheets (call_log tab)
Always: Send HTML call summary email to customer
If escalated: Send agent briefing email to human agent
If escalated: Post Slack alert to #insurvoice-alerts
```

The `insurvoice_n8n_workflow.json` in `mvp/web/` is the current production workflow.

---

## Tools Used

| Tool | POC role | MVP role |
|---|---|---|
| **Deepgram** | REST batch STT | Live WebSocket streaming STT |
| **n8n** | Core orchestrator | Post-call automation layer |
| **Claude** | Intent + response via n8n HTTP call | Intent + response via Python multi-agent |
| **ElevenLabs** | TTS via n8n HTTP call | TTS via Python `voice.py` |
| **Google Sheets** | Call log via n8n | Call log via n8n (same) |
| **Gmail** | Not in POC | Customer summary + agent briefing via n8n |
| **Slack** | Not in POC | Escalation alerts via n8n |
| **Supabase** | Not in POC | CRM database (customers + claims + call_log) |
| **Simli** | Not in POC | Lip-synced avatar |
| **Flask + SocketIO** | Not in POC | Web interface with browser mic |

---

## Reproducing the POC

### Prerequisites
- n8n account (n8n.cloud free trial or `npx n8n` locally)
- API keys: `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`

### Steps
1. Import `poc_workflow.json` into n8n
2. Set Anthropic credential: HTTP Header Auth → name: `x-api-key`
3. Activate workflow → copy webhook URL
4. POST to webhook:
```json
{
  "transcript": "Does my home insurance cover a burst pipe?",
  "conversation_id": "test-001",
  "turn_number": 1,
  "history": []
}
```
5. Receive response:
```json
{
  "response": "Hi, I am Tina, an AI assistant for Allianz Direct. Yes, burst pipe water damage is covered...",
  "intent": "policy_coverage",
  "escalated": false
}
```

**To run the full MVP instead:**
```bash
cd mvp/web
pip install -r requirements.txt
pip install psycopg2-binary langdetect
python server.py
# Open http://localhost:5000/avatar
```
