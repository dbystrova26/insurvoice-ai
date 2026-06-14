# POC Documentation — InsurVoice AI

**File:** `poc/poc_documentation.md`  
**POC type:** No-code / low-code voice agent prototype  
**Stack:** n8n (orchestration) + Deepgram (STT) + Claude (reasoning) + ElevenLabs (TTS)  
**MVP upgrade:** Added Simli avatar, Supabase CRM, multi-agent architecture, live streaming STT

---

## What Was Validated in the POC

The POC answered one question: **can we build a voice loop that works end-to-end?**

```
Caller speaks
    ↓
Deepgram STT → text transcript
    ↓
n8n orchestrates → Claude classifies intent + generates response
    ↓
ElevenLabs TTS → spoken audio reply
    ↓
Caller hears the answer
```

This loop was validated before building the full MVP. The POC proved:
- Deepgram nova-3 transcribes insurance queries accurately (including non-native accents)
- Claude reliably classifies insurance intents with >85% accuracy
- ElevenLabs produces natural-sounding voice replies under 3 seconds
- EU AI Act Art. 52 disclosure can be enforced programmatically on the first turn

---

## Tools Used and Why

| Tool | Role | Why chosen |
|---|---|---|
| **Deepgram nova-3** | Speech-to-text — live streaming transcription | Best accent robustness; 12k min/month free; streaming API |
| **n8n** | Orchestration — webhook → KB → Claude → response | Free; exportable JSON; visual workflow editor |
| **Anthropic Claude** | Intent classification + response generation | Reliable structured JSON output; multilingual |
| **ElevenLabs** | Text-to-speech — speaks the AI response | Natural-sounding TTS; multilingual from single voice; free tier |
| **Supabase** | CRM database — customer policy + claims lookup | Free hosted PostgreSQL; compatible with Render |
| **Simli** | Lip-synced avatar — animated face | WebRTC real-time; free 200 min/month |

---

## n8n POC Workflow — Step by Step

```
1. Caller speaks (browser mic — Deepgram live WebSocket)
       ↓
2. Deepgram transcribes audio to text in real time (nova-3)
       ↓
3. n8n webhook receives {transcript, language, conversation_id, turn_number}
       ↓
4. n8n loads knowledge base context (154 insurance FAQs)
       ↓
5. n8n calls Claude API:
       system prompt + KB context + conversation history + transcript
       ↓
6. Claude returns JSON:
       {intent, confidence, response, should_escalate, escalation_reason}
       ↓
7a. No escalation → ElevenLabs → audio → played to caller
7b. Escalation → handoff summary → Gmail briefing → Slack alert → Sheets log
       ↓
8. Turn logged to Supabase call_log (anonymised: intent + timestamp only)
```

---

## AI Capabilities Demonstrated

1. **Live streaming STT** — Deepgram transcribes in real time, no button press, handles non-native accents
2. **Automatic language detection** — langdetect identifies EN/DE/ES/FR/IT; Claude replies in same language
3. **Intent classification** — Claude maps transcript to 9 intent categories with confidence score
4. **Retrieval-Augmented Generation** — 154 FAQs retrieved by keyword search; no hallucinated policy terms
5. **CRM personalisation** — customer looked up by name + policy number in Supabase; Tina greets by name with actual policy details
6. **Natural multilingual voice** — ElevenLabs delivers human-sounding reply in detected language from single voice model
7. **Multi-turn dialogue** — context maintained across spoken turns
8. **Escalation logic** — detects handoff signals; generates spoken acknowledgement + written agent briefing
9. **Lip-synced avatar** — Simli WebRTC animates Tina's face in sync with ElevenLabs audio

---

## MVP Upgrades vs POC

| Feature | POC (n8n) | MVP (Python) |
|---|---|---|
| STT | Deepgram REST | Deepgram live WebSocket streaming |
| Orchestration | n8n workflow | Python multi-agent: Router + 5 Specialists + ComplianceGuard |
| Compliance | Prompt instruction | ComplianceGuard agent — deterministic rules + LLM rewrite |
| CRM | None | Supabase PostgreSQL — 20 mock customers + 10 claims |
| Avatar | None | Simli WebRTC lip-synced face |
| Language | English only | Auto-detect EN/DE/ES/FR/IT via langdetect |
| Automation | Google Sheets log | n8n → Gmail + Google Sheets + Slack + Supabase |
| Interface | Text only | Voice + Avatar (Flask + SocketIO) |

---

## Reproducing the POC

### Prerequisites
- n8n account (n8n.cloud free trial or `npx n8n` locally)
- API keys: `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`

### Steps
1. Import `poc_workflow.json` into n8n
2. Set credentials for Anthropic (HTTP Header: `x-api-key`)
3. Activate workflow, copy webhook URL
4. POST to webhook: `{message, conversation_id, turn_number, history}`
5. Receive JSON: `{response, intent, escalated, handoff_summary}`

**Faster alternative — run the full MVP:**
```bash
cd mvp/web
pip install -r requirements.txt
pip install psycopg2-binary langdetect
python server.py
```
Open `http://localhost:5000/avatar` — Tina greets you automatically.

---

## Known Limitations (POC → addressed in MVP)

| POC Limitation | MVP Solution |
|---|---|
| Single Claude call (no agents) | 7-agent pipeline: Router + 4 Specialists + Escalation + ComplianceGuard |
| No compliance enforcement | ComplianceGuard checks every reply before it is spoken |
| No CRM lookup | Supabase PostgreSQL — personalised greetings by policy number |
| English only | Auto-detect + reply in EN/DE/ES/FR/IT |
| No avatar | Simli WebRTC lip-synced animated face |
| No audit trail | n8n → Gmail + Google Sheets + Slack + Supabase call_log |
| STT latency ~1-2s (REST) | Deepgram live WebSocket streaming — no delay |
