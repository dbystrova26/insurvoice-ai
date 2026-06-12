# Use Case Definition — InsurVoice AI

**Company:** Allianz Direct GmbH (fictional scenario)  
**Student:** Daria Bystrova · Ironhack AI Consulting Bootcamp 2025  
**Delivery status:** ✅ MVP delivered — live voice agent with lip-synced avatar

---

## Business Context

Allianz Direct is a mid-size direct insurer operating across Germany and Austria. Their contact centre handles approximately 1,800 inbound customer calls per day. Analysis of call logs reveals:

- **68% are Tier-1 queries** — routine questions about policies, claims procedures, billing, and coverage that do not require human expertise
- **Average handle time:** 8.4 minutes per call
- **Annual contact centre cost:** ~EUR 2.1M (40 FTEs, fully loaded)
- **Customer satisfaction (CSAT):** 72% — dragged down by hold times exceeding 6 minutes during peak hours

The opportunity: deflect Tier-1 calls to an AI voice agent, freeing human agents for complex cases and reducing costs while improving response speed.

---

## Problem Statement

Customers calling for routine insurance queries face:
1. Long hold times (6+ min peak)
2. Inconsistent answers depending on which agent they reach
3. No out-of-hours availability (office hours only)
4. Language barriers — significant non-native German speaker population

---

## Proposed Solution — InsurVoice AI

A multi-agent AI voice system that:
- **Answers instantly** — no hold time
- **Operates 24/7** — claims emergencies don't follow business hours
- **Speaks the customer's language** — auto-detects EN, DE, ES, FR, IT
- **Hands off intelligently** — escalates to a human with a briefing when needed
- **Complies with EU AI Act and GDPR** — every reply checked before spoken

---

## Delivered MVP

The following has been designed, built, and tested:

### Voice Pipeline
```
Caller speaks
    ↓
Deepgram nova-3 (live streaming STT, accent-robust)
    ↓
langdetect (automatic language identification)
    ↓
Router agent → Specialist agent (Claude claude-opus-4-6)
    ↓
Compliance Guard (EU AI Act Art. 52 + GDPR check)
    ↓
ElevenLabs TTS (multilingual voice synthesis)
    ↓
Simli WebRTC (lip-synced avatar, optional)
    ↓
Caller hears and sees the response
```

### Interfaces
- **`/`** — Voice-only interface (mic orb, transcript panel, compliance badges)
- **`/avatar`** — Avatar interface (animated face, lip-synced, same pipeline)

### Multi-Agent Architecture
| Agent | Responsibility |
|---|---|
| Router | Classifies intent, delegates to correct specialist |
| Claims specialist | Filing claims, status, documents, timelines |
| Billing specialist | Premiums, payments, invoices, refunds |
| Policy specialist | Coverage, renewals, cancellations, changes |
| General specialist | Hours, contacts, portal, complaints |
| Escalation agent | Human handoff script + written agent briefing |
| Compliance Guard | Checks every reply for EU AI Act and GDPR compliance |
| Orchestrator | Manages context, history, language, and turn flow |

### Knowledge Base
154 realistic insurance FAQs across 7 categories: home insurance, claims, billing, policy management, liability, travel, and general. Retrieved via keyword RAG per query.

### Compliance
- **EU AI Act Art. 52** — system identifies itself as AI on every first turn; enforced at runtime
- **GDPR** — voice audio processed in-session and not retained; no biometric profiling; data minimisation applied

---

## Success Metrics

| Metric | Target | Measured |
|---|---|---|
| Intent routing accuracy | ≥ 85% | Run `python evaluate.py` |
| Keyword coverage in responses | ≥ 70% | Run `python evaluate.py` |
| EU AI Act compliance rate | 100% | Enforced by ComplianceGuard |
| Tier-1 deflection potential | 60%+ | Based on pilot routing data |
| Response latency | < 5 seconds | ~3.2s avg in testing |

---

## Business Case Summary

Deflecting 60% of 1,800 daily Tier-1 calls at EUR 3.20 cost-per-call savings:

| Scenario | Annual Saving |
|---|---|
| 40% deflection | ~EUR 840K |
| 60% deflection | ~EUR 1.26M |
| 75% deflection | ~EUR 1.58M |

AI system cost at scale: ~EUR 80–120K/year (API costs + infrastructure).  
**Net ROI at 60% deflection: ~EUR 1.14M/year** (first year, after setup costs).

---

## What Is Out of Scope (Future Phases)

- CRM integration (live policy lookup, account authentication)
- Outbound proactive call capability
- Full IVR/telephony integration (Twilio/Vonage)
- Fine-tuned domain-specific LLM
- Real-time sentiment analysis for agent coaching
