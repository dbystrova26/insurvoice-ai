# GDPR Documentation — InsurVoice AI

**File:** `compliance/gdpr_documentation.md`  
**System:** InsurVoice AI — Conversational AI Customer Service Agent  
**Author:** Daria Bystrova | Ironhack AI Consulting Bootcamp | June 2025  
**Regulation:** GDPR — Regulation (EU) 2016/679

---

## Part 1: Data Flow Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW OVERVIEW                          │
└─────────────────────────────────────────────────────────────────────┘

CUSTOMER                    ALLIANZ DIRECT               THIRD PARTIES
(Data Subject)              (Data Controller)

    │                             │
    │ Chat message                │
    │ (text content,         ┌────▼────────────┐
    │  may contain           │  Voiceflow      │ ──── Session data (EU servers)
    │  policy number,        │  (Dialogue UI)  │
    │  personal details)     └────┬────────────┘
    │                             │ Webhook (message text + conv_id)
    │                        ┌────▼────────────┐
    │                        │  n8n            │ ──── Execution logs (EU/self-hosted)
    │                        │  (Orchestrator) │
    │                        └────┬────────────┘
    │                             │ API call (message + KB context)
    │                             │ NO policy number, NO name sent
    │                        ┌────▼────────────┐
    │                        │  Anthropic API  │ ──── USA (SCCs apply)
    │                        │  (Claude)       │      DPA executed
    │                        └────┬────────────┘
    │                             │ Response text
    │                        ┌────▼────────────┐
    │ ◄── Response text ─────│  Response       │
    │                        │  delivered      │
    │                        └────┬────────────┘
    │                             │ Anonymised log entry
    │                        ┌────▼────────────┐
    │                        │  Google Sheets  │ ──── EU region
    │                        │  (Audit log)    │      No personal data
    │                        └─────────────────┘

KEY:
→  Personal data may flow
──► Non-personal / anonymised data only
```

**Critical design note:** The system is designed to minimise personal data transmission. The Anthropic API receives only the conversation message text and knowledge base context. Policy numbers, names, and contact details are **not** extracted or forwarded — if a customer mentions them in their message, they appear in the message text but are not stored after the session.

---

## Part 2: Processing Activities Register

| # | Data element | Personal data? | Purpose | Legal basis (Art. 6) | Retention | Third-party recipients |
|---|---|---|---|---|---|---|
| 1 | **Chat message text** | Possibly — customer may mention name, policy number, address | Responding to customer query; intent classification | Art. 6(1)(b) — performance of contract (insurance policy) | Session only — not stored after response sent | Anthropic API (see Part 5) |
| 2 | **Conversation ID** | No — randomly generated UUID | Session continuity; audit trail | Art. 6(1)(f) — legitimate interest (service quality) | 30 days | Google Sheets (anonymised log) |
| 3 | **Intent classification result** | No — category label only (e.g. "policy_coverage") | Quality monitoring; system improvement | Art. 6(1)(f) — legitimate interest | 30 days | Google Sheets |
| 4 | **Escalation flag + reason** | No — structured flag only | Routing to human agent; audit | Art. 6(1)(b) — performance of contract | 30 days | None (internal only) |
| 5 | **Handoff summary** (if escalated) | Yes — may summarise personal details mentioned | Enabling human agent to continue conversation without customer repeating | Art. 6(1)(b) — performance of contract | Until agent closes ticket (max 7 days) | None (internal only) |
| 6 | **Voiceflow session data** | Minimal — session tokens, no personal data by design | Dialogue state management | Art. 6(1)(b) — contract | Session only | Voiceflow (EU servers) |
| 7 | **Agent user accounts** (future v2) | Yes — name, email, role | Authentication and access control | Art. 6(1)(b) — employment contract | Duration of employment + 30 days | None |

---

## Part 3: Data Protection Impact Assessment (DPIA)

**Scope of this DPIA:** Real-time chat message processing and transmission to Anthropic API — identified as the highest-risk processing activity because: (a) messages may contain personal data including special category data (health details in claims queries), and (b) data is transmitted to a third-party processor based in the USA.

### 3.1 Description of Processing

- **Nature:** Customer sends free-text message via voice and chat interface. Message text is transmitted in real time to Anthropic's Claude API for intent classification and response generation.
- **Purpose:** Enabling the AI agent to understand and respond to customer queries
- **Scope:** Up to 2,400 contacts/day; text messages averaging ~80 characters
- **Data subjects:** Insurance customers (adults; no special targeting of vulnerable persons)
- **Special category data risk:** Customers querying about health insurance or medical claims may include health information in their message (Article 9 GDPR). This is the highest-risk element of this DPIA.

### 3.2 Necessity and Proportionality Assessment

| Test | Assessment |
|---|---|
| **Necessity** | Transmission to Claude API is necessary — the LLM cannot run locally at this scale. Alternative: fine-tuned open-source model self-hosted (eliminates third-party transfer but increases cost and reduces quality). This is the Phase 3 option if regulatory pressure increases. |
| **Proportionality** | Message text only is transmitted — no policy number extraction, no name lookup, no CRM data. The minimum necessary data is sent. Character limit (500 chars) enforced. |
| **Could the purpose be achieved with less data?** | Partially. A simpler rule-based intent classifier could handle ~40% of intents without LLM. Hybrid approach considered for Phase 2. |

### 3.3 Risks to Data Subjects

| Risk | Likelihood | Impact | Level |
|---|---|---|---|
| Health data (Art. 9) transmitted to US processor without explicit consent | Medium | High | **High** |
| Message content used by Anthropic to train future models | Low (DPA prohibits) | High | Medium |
| Data intercepted in transit | Low (TLS 1.3) | High | Low |
| Conversation log linked back to individual | Low (no PII in log) | Medium | Low |
| System retains data beyond stated retention period | Low (no storage in MVP) | Medium | Low |

### 3.4 Mitigation Measures

| Risk | Mitigation | Status |
|---|---|---|
| Health data transmitted to US processor | (1) Anthropic DPA executed with SCCs (Module 2 — Controller to Processor); (2) System prompt instructs Claude to ignore/not store health details; (3) Phase 2: add pre-processing filter to redact Art. 9 data before API call | Partially implemented |
| Model training on API inputs | Anthropic API Terms + DPA explicitly prohibit using API inputs for model training. Verify in DPA before go-live. | Requires DPA execution |
| Data interception | HTTPS/TLS 1.3 enforced; certificate pinning in production | TLS implemented in MVP |
| Retention | No personal data stored beyond session in current implementation. Log contains only: timestamp, conv_id, intent, escalation_flag — no message content. | ✅ Implemented |

### 3.5 Residual Risk Rating

After mitigations: **Medium overall**. The health data transmission risk remains the key open item — it is mitigated by the Anthropic DPA and SCCs but not eliminated. A production deployment should add an Art. 9 data detection filter. No prior consultation with the supervisory authority (BfDI — Federal Commissioner for Data Protection) is required at current risk level, but should be considered if the system is expanded to process health insurance claims.

---

## Part 4: Data Subject Rights

| Right | GDPR Article | Applicability | How the system supports it |
|---|---|---|---|
| **Right of access** | Art. 15 | Applies — customers may request to know what data was processed | Current MVP: no persistent personal data stored — right trivially satisfied. v2 with logs: data subject access request (DSAR) portal to be built. Contact: privacy@allianz-direct.example.de |
| **Right to erasure** | Art. 17 | Applies | Current MVP: no storage — erasure trivially satisfied. v2: conversation logs deleted on request within 72 hours. |
| **Right to rectification** | Art. 16 | Limited applicability — system doesn't store profile data | If inaccurate data appears in a handoff summary, agent corrects it before use. |
| **Right to portability** | Art. 20 | Applies where Art. 6(1)(b) is legal basis | Conversation transcript can be provided on request (email) in JSON or plain text. |
| **Right to object** | Art. 21 | Applies where legitimate interest is legal basis | Customers may object to AI handling their contact — they can request human agent at any time without restriction. |
| **Right not to be subject to solely automated decisions (Art. 22)** | Art. 22 | **Key right for this system** | **Fully satisfied by design: InsurVoice makes no decisions. Human escalation is always available. No binding determination is ever made by the AI.** |
| **Right to withdraw consent** | Art. 7 | Not applicable — legal basis is contract, not consent | N/A |

---

## Part 5: Third-Party Data Transfers

| Processor | Data sent | Transfer mechanism | Data location | DPA in place? |
|---|---|---|---|---|
| **Anthropic, Inc.** | Chat message text (may contain incidental personal data) | Standard Contractual Clauses — Module 2 (Controller to Processor) | USA | Required before go-live — Anthropic DPA available at anthropic.com/legal |
| **Voiceflow, Inc.** | Session tokens, dialogue state (no personal data by design) | SCCs | Canada/USA | Voiceflow DPA available; review before go-live |
| **Google LLC** (Sheets) | Anonymised log entries — conv_id, intent, timestamp only. No message content, no personal identifiers | EU adequacy decision + Google Workspace DPA | EU region selected | Google Workspace DPA — standard terms |
| **Railway** (hosting) | Application code, environment variables (no personal data) | EU hosting region selected | EU (Frankfurt) | Railway DPA available |

**Note on Anthropic:** Anthropic's API Terms of Service (as of 2024) explicitly state that inputs to the API are not used for model training. This must be confirmed in the executed DPA before processing personal data. If confirmation cannot be obtained, the fallback is to implement a PII-stripping pre-processor that removes personal data from messages before transmission.


---

## Part 6: Voice-Specific Data Considerations (CRITICAL FOR THIS SYSTEM)

Because InsurVoice processes **audio recordings of the caller's voice**, additional GDPR considerations apply that do not apply to a text-only chatbot. This is the single most important difference for a voice agent.

### 6.1 Is voice data biometric data?

A voice recording is **personal data** under Article 4(1). It becomes **biometric data** under Article 4(14) — a special category under Article 9 — *only if processed for the purpose of uniquely identifying a person* (e.g. voiceprint authentication).

| Use of voice | Classification | Applies to InsurVoice? |
|---|---|---|
| Recording voice to transcribe content | Personal data (Art. 4(1)) | ✅ Yes — this is what we do |
| Voiceprint analysis to identify/authenticate the speaker | Biometric special category data (Art. 9) | ❌ No — we do NOT do voiceprint identification |

**Conclusion:** InsurVoice processes voice as ordinary personal data, NOT Article 9 biometric data, because it transcribes *what is said*, not *who is speaking*. This is a deliberate design choice to avoid triggering Article 9 obligations. If voiceprint authentication were added in future, a full Article 9 assessment and explicit consent would be required.

### 6.2 Voice data flow

| Stage | What happens to the audio | Retention |
|---|---|---|
| Capture | Browser records audio (mic) or user uploads file | In-memory only |
| Transcription | Audio bytes sent to OpenAI Whisper API → returns text | OpenAI: not retained for training (per API terms); deleted after processing |
| After transcription | Audio bytes discarded; only text proceeds through pipeline | Audio NOT stored on InsurVoice servers |
| Response | ElevenLabs generates response audio from text | Generated audio served to browser, not stored |

**Key design principle:** the raw voice recording is **never persisted**. It exists only transiently to be transcribed, then is discarded. Only the transcribed text (and ultimately only the intent label) is retained.

### 6.3 Additional third-party processor: OpenAI

| Processor | Data sent | Mechanism | Location | Note |
|---|---|---|---|---|
| OpenAI (Whisper STT) | Caller's voice recording (audio bytes) | SCCs (Module 2) | USA | OpenAI API data not used for training per API terms (March 2023 policy). DPA required before production. |
| ElevenLabs (TTS) | Response text only (NOT the caller's voice) | SCCs | USA/EU | Only synthetic response text sent; no caller personal data. |

### 6.4 Updated DPIA residual risk

The transmission of voice recordings to OpenAI (US) is now the **highest-risk processing activity**, replacing text transmission. Mitigations:
- Audio transcribed then immediately discarded — minimal retention
- OpenAI DPA + SCCs before production
- Caller informed at call start that the call is AI-handled (Art. 52 disclosure doubles as transparency)
- Production: offer on-premise Whisper (self-hosted, open-source model) to eliminate US transfer entirely — this is the recommended Phase 3 enhancement

**Residual risk: Medium.** The voice-to-US-processor transfer is the key open item; self-hosting Whisper in production reduces it to Low.
