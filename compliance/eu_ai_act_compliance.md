# EU AI Act Compliance Documentation — InsurVoice AI

**File:** `compliance/eu_ai_act_compliance.md`  
**System:** InsurVoice AI — Conversational AI Customer Service Agent  
**Author:** Daria Bystrova | Ironhack AI Consulting Bootcamp | June 2026  
**Regulation:** EU AI Act — Regulation (EU) 2024/1689, in force August 2024

---

## Part A: Risk Classification

### A.1 Classification Result

> **RISK LEVEL: LIMITED RISK**  
> **Applicable obligations: Article 52(1) — transparency to natural persons**

### A.2 Step-by-Step Classification Reasoning

#### Step 1: Screen for Unacceptable Risk (Article 5)

The following prohibited practices were checked:

| Prohibited practice | Applies? | Reasoning |
|---|---|---|
| Subliminal manipulation techniques | ❌ No | System responds to explicit queries; no persuasion beyond answering questions |
| Exploitation of vulnerability (age, disability, etc.) | ❌ No | System treats all users identically; no targeting of vulnerable groups |
| Social scoring by public authority | ❌ No | Private insurance company; not a public authority |
| Real-time remote biometric identification in public spaces | ❌ No | Text/voice chat only; no biometric identification |
| Emotion recognition in workplace/education | ❌ No | Customer service context, not workplace/education |

**Conclusion: Not unacceptable risk. Proceed to Step 2.**

---

#### Step 2: Screen for High Risk (Annex III)

All Annex III categories reviewed:

| Annex III category | Applies? | Reasoning |
|---|---|---|
| 1. Biometric identification | ❌ No | No biometrics used |
| 2. Critical infrastructure | ❌ No | Insurance contact centre is not critical infrastructure |
| 3. Education / vocational training | ❌ No | Not applicable |
| 4. Employment and workers management | ❌ No | Not used for HR decisions |
| **5(b). Creditworthiness / credit score assessment** | **⚠️ Reviewed carefully** | **System provides information about existing policies only. It does NOT assess creditworthiness, set premiums, accept/reject claims, or make any underwriting decisions. Scope is explicitly limited to FAQ-style information retrieval. Not Annex III.** |
| 5(c). Life/health insurance risk assessment | ❌ Not applicable | No risk assessment performed |
| 6. Access to essential services | ❌ No | Insurance service access decisions not made by AI |
| 7. Law enforcement | ❌ No | Not applicable |
| 8. Migration / border control | ❌ No | Not applicable |
| 9. Administration of justice | ❌ No | Not applicable |

**Key argument for non-high-risk:** The most proximate Annex III category is 5(b) (AI systems used to evaluate creditworthiness or establish credit scores of natural persons). InsurVoice AI is explicitly out of scope for any evaluation or decision function. It cannot accept or reject claims, modify policy terms, or make any determination that affects a customer's insurance relationship. It answers questions. This is analogous to a search engine over a knowledge base — not a decision system.

**Conclusion: Not high risk. Proceed to Step 3.**

---

#### Step 3: Identify Limited Risk Obligations (Article 52)

**Article 52(1)** applies: AI systems intended to interact with natural persons must ensure those persons are informed they are interacting with an AI system at the beginning of the interaction.

**Article 52(3)** applies: AI-generated content must be clearly labelled as AI-generated where there is a reasonable risk of confusion about its origin.

**Conclusion: LIMITED RISK — Article 52(1) and 52(3) transparency obligations apply.**

---

#### Step 4: Financial Services Context

As InsurVoice is deployed within an insurance company, additional regulatory context:

- **BaFin AI guidelines (2024):** BaFin expects firms to ensure AI-generated customer communications are accurate, fair, and non-misleading. InsurVoice's RAG architecture grounds all responses in verified KB content, satisfying this requirement.
- **IDD (Insurance Distribution Directive):** InsurVoice does not provide insurance advice or recommendations — it provides factual information about existing policy terms. This keeps it outside IDD scope.
- **EIOPA guidelines on AI governance:** Require human oversight of AI systems in insurance. The mandatory escalation mechanism and QA audit satisfy this.

---

## Part B: Mandatory Requirements Summary (Limited Risk)

Even as limited risk, best-practice implementation addresses the requirements that would be mandatory if high-risk:

### B.1 Data and Data Governance

| Requirement | Implementation |
|---|---|
| Training data quality | No training performed — uses pre-trained Claude model via API. KB content is human-authored and QA-reviewed before deployment. |
| Input data validation | User messages checked for length (max 500 chars), content policy applied by Claude system prompt |
| Knowledge base governance | KB content reviewed and approved by insurance subject matter expert before go-live. Quarterly review cycle. |
| Data minimisation | System does not request or store policy numbers, personal details, or sensitive data unless customer volunteers them. |

### B.2 Human Oversight Mechanisms

| Mechanism | Implementation |
|---|---|
| Human always available | "Speak to a person" option available at every turn — no dead ends |
| Auto-escalation | After 2 failed classifications → auto-escalate; for any claim-decision request → auto-escalate; for complaints → auto-escalate |
| QA audit | 10% of conversations reviewed monthly by human QA agent |
| Override capability | Any agent can flag a conversation for review; flagged conversations excluded from AI handling the following day |

### B.3 Transparency and Information Obligations

| Obligation | Implementation |
|---|---|
| AI disclosure (Art. 52(1)) | **Implemented.** Opening message: *"Hi, I'm InsurVoice, an AI assistant for Allianz Direct. I'm an AI — how can I help?"* |
| AI content labelling | All chat responses include "InsurVoice AI" label in UI |
| User information | Privacy notice link in chat footer; system prompt instructs Claude never to deny being an AI if asked directly |
| Escalation transparency | When escalating, system explicitly states "I'm connecting you to a human agent" |

### B.4 Accuracy and Robustness Requirements

| Requirement | Implementation |
|---|---|
| Accuracy testing | Parallel testing: 50 test cases against KB before each deployment. Acceptance threshold: 92% correct answers. |
| Robustness to adversarial input | Claude system prompt hardened; output constrained to KB; unknown queries handled with honest "I don't know" |
| Fallback behaviour | If API call fails: graceful error message + immediate human escalation |
| Monitoring | n8n execution logs; monthly accuracy audit; CSAT tracked per conversation |

### B.5 Cybersecurity Considerations

| Risk | Mitigation |
|---|---|
| Prompt injection attacks | System prompt instructs Claude to ignore instructions embedded in user messages; tested against common injection patterns |
| API key exposure | Keys stored as environment variables; never in code; .env.example in repo |
| Conversation data interception | HTTPS only; Anthropic API uses TLS 1.3 |
| Unauthorised access to logs | Google Sheets access restricted to ops team; conversation IDs not linked to personal identity |

---

## Part C: Conformity Assessment Summary

### System Description

InsurVoice AI is a conversational AI customer service agent deployed by Allianz Direct GmbH (fictional) to handle Tier-1 insurance customer contacts. The system classifies customer intent, retrieves relevant information from a curated knowledge base, and generates natural language responses. It is deployed via a Flask + SocketIO web interface with n8n automation, using Anthropic Claude claude-opus-4-6 as the underlying language model and Deepgram nova-3 for speech-to-text.

### Risk Class and Basis

**Limited Risk — Article 52(1) EU AI Act**

The system interacts with natural persons (insurance customers) via voice and chat interface. It does not make decisions, assess creditworthiness, process special category data, or perform any function listed in Annex III. Its sole function is information retrieval and natural language response generation.

### Applicable Obligations and Design Response

| Obligation | Status | How addressed |
|---|---|---|
| Art. 52(1) — AI disclosure at first interaction | ✅ Implemented | Opening message explicitly identifies system as AI |
| Art. 52(3) — AI content labelling | ✅ Implemented | "InsurVoice AI" label on all responses in UI |
| No binding automated decisions | ✅ By design | System scoped to information only; claim/policy decisions always route to human |
| Human escalation always available | ✅ By design | "Speak to a person" available every turn; auto-escalation after 2 failures |

### Gaps (to be resolved before production deployment)

| Gap | Resolution plan | Target phase |
|---|---|---|
| No formal conformity declaration (Art. 47) | Not required for limited risk, but will be drafted as best practice | Phase 2 pilot |
| No formal incident reporting procedure (Art. 73) | Draft incident log template and response procedure | Phase 2 pilot |
| Voice channel not yet assessed for production telephony | When Twilio voice is added, re-run classification | Phase 3 |
| Post-market monitoring plan | Formalise monthly QA audit into documented procedure | Phase 2 pilot |

---

## Part D: Technical Documentation Outline

*This table of contents describes the full technical documentation package for a production deployment. Sections marked Complete are drafted; others are scoped.*

| § | Section | Status |
|---|---|---|
| 1 | General system description — purpose, intended use, known limitations | ✅ Complete (use_case_definition.md) |
| 2 | Intended deployment context — industry, user types, geographic scope | ✅ Complete |
| 3 | Risk classification with step-by-step reasoning | ✅ Complete (this document) |
| 4 | System architecture — Flask + n8n + Claude API data flow diagram | ✅ Complete (architecture.png + README) |
| 5 | Underlying AI model — Claude claude-opus-4-6, Anthropic; general-purpose LLM; not fine-tuned | ✅ Complete |
| 6 | Knowledge base governance — content authoring, QA, update cycle | Partial |
| 7 | Input/output specification — message format, response schema, escalation flags | ✅ Complete (poc_workflow.json) |
| 8 | Human oversight mechanisms — escalation logic, QA audit procedure | ✅ Complete |
| 9 | Transparency measures — UI disclosure implementation | ✅ Complete |
| 10 | Accuracy testing methodology — test case set, acceptance threshold, retest criteria | ✅ Partial (evaluate.py, 30 test cases) |
| 11 | Robustness and adversarial testing — injection tests, edge case handling | Scoped for production |
| 12 | Cybersecurity measures — key management, TLS, access control | Scoped for production |
| 13 | Post-market monitoring plan — metrics, alert thresholds, review cadence | Scoped for production |
| 14 | Incident and serious incident reporting procedure (Art. 73) | Scoped for production |
| 15 | Conformity Assessment Summary (this document, Part C) | ✅ Complete |
| 16 | EU Declaration of Conformity (Art. 47) — production only | Scoped for production |

---

## Part E: Voice Channel Assessment (InsurVoice-specific)

Because InsurVoice operates as a **voice agent** (not text-only), the following voice-specific points were assessed:

| Question | Finding |
|---|---|
| Does voice processing trigger Annex III biometric category (point 1)? | **No.** Annex III point 1 covers biometric *identification/categorisation*. InsurVoice transcribes speech content (what is said) via Deepgram nova-3; it does not identify or categorise speakers by voiceprint. Speech-to-text is not biometric identification. |
| Does the AI voice need additional disclosure? | **Yes — and it's stronger for voice.** Art. 52(1) disclosure is delivered audibly at call start: "Hello, you're speaking with InsurVoice, an AI assistant." A caller cannot see a screen label, so the spoken disclosure is essential. |
| Does synthetic voice output need labelling (Art. 52(3))? | **Yes.** The AI-generated voice (ElevenLabs) is clearly identified as AI at the start; callers are never misled into believing they speak to a human. |
| Deepfake / voice-cloning concerns? | InsurVoice uses a generic synthetic voice (ElevenLabs stock voice), NOT a clone of any real person. No impersonation risk. |

**Conclusion:** the voice channel does not change the Limited Risk classification. It strengthens the importance of the Article 52 audible disclosure, which is implemented at the start of every call.
