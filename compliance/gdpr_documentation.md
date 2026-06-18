# GDPR Documentation — InsurVoice AI

**File:** `compliance/gdpr_documentation.md`  
**System:** InsurVoice AI — Conversational AI Customer Service Agent  
**Author:** Daria Bystrova | Ironhack AI Consulting Bootcamp | June 2026  
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
    │ Voice / text                │
    │ (audio stream or       ┌────▼────────────┐
    │  typed message,        │  Flask +        │
    │  may contain           │  SocketIO       │ ──── Render.com (EU Frankfurt)
    │  policy number,        │  (Web interface)│
    │  personal details)     └────┬────────────┘
    │                             │ Audio stream (STT)
    │                        ┌────▼────────────┐
    │                        │  Deepgram       │ ──── USA (SCCs apply)
    │                        │  nova-3 (STT)   │      DPA executed
    │                        └────┬────────────┘
    │                             │ Transcript text only
    │                        ┌────▼────────────┐
    │                        │  n8n            │ ──── Execution logs (EU/self-hosted)
    │                        │  (Orchestrator) │
    │                        └────┬────────────┘
    │                             │ API call (transcript + KB context)
    │                             │ NO policy number, NO name sent separately
    │                        ┌────▼────────────┐
    │                        │  Anthropic API  │ ──── USA (SCCs apply)
    │                        │  (Claude)       │      DPA executed
    │                        └────┬────────────┘
    │                             │ Response text
    │                        ┌────▼────────────┐
    │                        │  ElevenLabs TTS │ ──── USA/EU (SCCs apply)
    │                        │  (response only)│      No caller data sent
    │                        └────┬────────────┘
    │ ◄── Audio response ─────────┘
    │                        ┌────▼────────────┐
    │                        │  Google Sheets  │ ──── EU region
    │                        │  (Audit log)    │      No personal data
    │                        └─────────────────┘

KEY:
→  Personal data may flow
──► Non-personal / anonymised data only
```

**Critical design note:** The system is designed to minimise personal data transmission. The Anthropic API receives only the transcribed conversation text and knowledge base context — not raw audio, not extracted identifiers. Policy numbers and names are not stored after the session ends. Raw audio is discarded immediately after transcription by Deepgram.

---

## Part 2: Processing Activities Register

| # | Data element | Personal data? | Purpose | Legal basis (Art. 6) | Retention | Third-party recipients |
|---|---|---|---|---|---|---|
| 1 | **Voice audio stream** | Yes — voice recording is personal data | Speech-to-text transcription only | Art. 6(1)(b) — performance of contract | Session only — discarded after transcription | Deepgram (STT) |
| 2 | **Transcribed message text** | Possibly — customer may mention name, policy number, address | Responding to customer query; intent classification | Art. 6(1)(b) — performance of contract | Session only — not stored after response sent | Anthropic API |
| 3 | **Conversation ID** | No — randomly generated UUID | Session continuity; audit trail | Art. 6(1)(f) — legitimate interest (service quality) | 30 days | Google Sheets (anonymised log) |
| 4 | **Intent classification result** | No — category label only (e.g. "policy_coverage") | Quality monitoring; system improvement | Art. 6(1)(f) — legitimate interest | 30 days | Google Sheets |
| 5 | **Escalation flag + reason** | No — structured flag only | Routing to human agent; audit | Art. 6(1)(b) — performance of contract | 30 days | None (internal only) |
| 6 | **Handoff summary** (if escalated) | Yes — may summarise personal details mentioned | Enabling human agent to continue without customer repeating | Art. 6(1)(b) — performance of contract | Until agent closes ticket (max 7 days) | None (internal only) |
| 7 | **Agent user accounts** (future v2) | Yes — name, email, role | Authentication and access control | Art. 6(1)(b) — employment contract | Duration of employment + 30 days | None |

---

## Part 3: Data Protection Impact Assessment (DPIA)

**Scope of this DPIA:** Voice audio processing and transmission to Deepgram for transcription, followed by transcribed text transmission to Anthropic API — identified as the two highest-risk processing activities because: (a) audio recordings are personal data, (b) transcripts may contain special category data (health details in claims queries), and (c) both processors are based in the USA.

### 3.1 Description of Processing

- **Nature:** Customer speaks via browser microphone (or types). Audio stream is sent in real time to Deepgram nova-3 for live transcription. Transcribed text is then sent to Anthropic's Claude API for intent classification and response generation.
- **Purpose:** Enabling the AI agent to hear, understand, and respond to customer queries
- **Scope:** Up to 2,400 contacts/day; audio streams averaging ~60 seconds per interaction
- **Data subjects:** Insurance customers (adults; no special targeting of vulnerable persons)
- **Special category data risk:** Customers querying about health insurance or medical claims may include health information in spoken or written messages (Article 9 GDPR). This is the highest-risk element of this DPIA.

### 3.2 Necessity and Proportionality Assessment

| Test | Assessment |
|---|---|
| **Necessity** | Transmission to Deepgram is necessary for live speech transcription — no viable on-premise alternative at this latency. Production option: self-hosted Whisper (open-source) to eliminate US transfer. |
| **Proportionality** | Audio is transmitted for transcription only and immediately discarded — not stored. Transcribed text only (not audio) is forwarded to Claude API. Character limit (500 chars) enforced on text input. |
| **Could the purpose be achieved with less data?** | Partially. Text-only input eliminates the audio transfer entirely. The text fallback is always available in the UI. |

### 3.3 Risks to Data Subjects

| Risk | Likelihood | Impact | Level |
|---|---|---|---|
| Health data (Art. 9) in spoken content transmitted to US processors | Medium | High | **High** |
| Audio recordings used by Deepgram to train future models | Low (DPA prohibits) | High | Medium |
| Message content used by Anthropic to train future models | Low (DPA prohibits) | High | Medium |
| Data intercepted in transit | Low (TLS 1.3) | High | Low |
| Conversation log linked back to individual | Low (no PII in log) | Medium | Low |
| System retains data beyond stated retention period | Low (no storage in MVP) | Medium | Low |

### 3.4 Mitigation Measures

| Risk | Mitigation | Status |
|---|---|---|
| Health data in audio/text to US processors | (1) Deepgram DPA + SCCs executed; (2) Anthropic DPA + SCCs executed; (3) Phase 2: add pre-processing filter to detect and redact Art. 9 data before API calls; (4) Phase 3: self-host Whisper to eliminate audio US transfer | Partially implemented |
| Model training on inputs | Deepgram and Anthropic API terms prohibit using API inputs for model training. Verify in executed DPAs before go-live. | Requires DPA execution |
| Data interception | HTTPS/TLS 1.3 enforced across all API calls | ✅ Implemented in MVP |
| Retention | No audio stored beyond session. Log contains only: timestamp, conv_id, intent, escalation_flag — no message content, no audio. | ✅ Implemented |

### 3.5 Residual Risk Rating

After mitigations: **Medium overall**. The health data transmission risk via audio (Deepgram) and text (Anthropic) to US processors is the key open item — mitigated by DPAs and SCCs but not eliminated. A production deployment should add an Art. 9 data detection filter. Self-hosting Whisper in Phase 3 would reduce audio risk to Low.

---

## Part 4: Data Subject Rights

| Right | GDPR Article | Applicability | How the system supports it |
|---|---|---|---|
| **Right of access** | Art. 15 | Applies | Current MVP: no persistent personal data stored — right trivially satisfied. v2 with logs: DSAR portal to be built. |
| **Right to erasure** | Art. 17 | Applies | Current MVP: no storage — erasure trivially satisfied. v2: conversation logs deleted on request within 72 hours. |
| **Right to rectification** | Art. 16 | Limited — system doesn't store profile data | If inaccurate data appears in a handoff summary, agent corrects it before use. |
| **Right to portability** | Art. 20 | Applies where Art. 6(1)(b) is legal basis | Conversation transcript can be provided on request in JSON or plain text. |
| **Right to object** | Art. 21 | Applies where legitimate interest is legal basis | Customers may object to AI handling — they can request a human agent at any turn without restriction. |
| **Right not to be subject to solely automated decisions** | Art. 22 | **Key right for this system** | **Fully satisfied by design: InsurVoice makes no decisions. Human escalation always available. No binding determination ever made by the AI.** |
| **Right to withdraw consent** | Art. 7 | Not applicable — legal basis is contract, not consent | N/A |

---

## Part 5: Third-Party Data Transfers

| Processor | Data sent | Transfer mechanism | Data location | DPA in place? |
|---|---|---|---|---|
| **Deepgram, Inc.** | Voice audio stream (real-time, then discarded) | Standard Contractual Clauses — Module 2 | USA | Required before go-live — Deepgram DPA available at deepgram.com/legal |
| **Anthropic, Inc.** | Transcribed message text (may contain incidental personal data) | Standard Contractual Clauses — Module 2 | USA | Required before go-live — Anthropic DPA available at anthropic.com/legal |
| **ElevenLabs** | Response text only — NOT the caller's voice or transcript | SCCs | USA/EU | ElevenLabs DPA available; review before go-live |
| **Google LLC** (Sheets) | Anonymised log entries — conv_id, intent, timestamp only. No audio, no transcript, no personal identifiers | EU adequacy decision + Google Workspace DPA | EU region selected | Google Workspace DPA — standard terms |
| **Render.com** | Application code, environment variables (no personal data) | EU hosting region selected | EU (Frankfurt) | Render DPA available |

**Note on Deepgram:** Deepgram's API Terms (as of 2024) explicitly state that API inputs are not used for model training. This must be confirmed in the executed DPA before processing audio containing personal data. If confirmation cannot be obtained, the fallback is to self-host Deepgram's on-premise offering or switch to self-hosted Whisper.

**Note on Anthropic:** Same position — API inputs not used for training per API terms. Must be confirmed in executed DPA.

---

## Part 6: Voice-Specific Data Considerations (Critical for This System)

Because InsurVoice processes **live audio recordings of the caller's voice** via Deepgram nova-3, additional GDPR considerations apply that do not apply to a text-only chatbot.

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
| Capture | Browser records audio via mic; audio streamed over WebSocket | In-memory only |
| Transcription | Audio bytes sent to Deepgram nova-3 API → returns text transcript | Deepgram: not retained for training (per API terms); deleted after processing |
| After transcription | Audio bytes discarded; only transcribed text proceeds through pipeline | Audio NOT stored on InsurVoice servers |
| Response | ElevenLabs generates response audio from text only | Generated audio served to browser, not stored |

**Key design principle:** the raw voice recording is **never persisted**. It exists only transiently to be transcribed, then is discarded. Only the transcribed text (and ultimately only the intent label) is retained.

### 6.3 STT processor: Deepgram

| Processor | Data sent | Mechanism | Location | Note |
|---|---|---|---|---|
| Deepgram (nova-3 STT) | Caller's voice audio (live stream) | SCCs (Module 2) | USA | API inputs not used for training per Deepgram API terms. DPA required before production. Phase 3 option: self-hosted Deepgram or open-source Whisper to eliminate transfer. |
| ElevenLabs (TTS) | Response text only (NOT the caller's voice) | SCCs | USA/EU | Only AI-generated response text sent; no caller personal data transmitted. |

### 6.4 Updated DPIA residual risk

The live transmission of voice audio to Deepgram (US) is the **highest-risk processing activity** in the system. Mitigations:

- Audio transcribed in real time then immediately discarded — minimal retention window
- Deepgram DPA + SCCs before production go-live
- Caller informed at call start that the call is AI-handled (Art. 52 disclosure doubles as transparency notice)
- Text input fallback always available — eliminates audio transfer entirely for users who prefer it
- Phase 3: self-hosted Whisper (open-source, no external transfer) reduces this risk to Low

**Residual risk: Medium.** The voice-to-US-processor transfer is the key open item; self-hosting in production reduces it to Low.
