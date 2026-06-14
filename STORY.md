# The Story Behind InsurVoice AI

*By Daria Bystrova · Ironhack AI Consulting Bootcamp · 2025*

---

## Why Insurance

I did not pick insurance because I find it exciting. I picked it because almost nobody does — and that is exactly the point.

Insurance is one of the most important financial products in most people's lives, and one of the most frustrating to deal with. You call a contact centre when something bad has already happened — your flat flooded, your phone was stolen, you had an accident. You are stressed. You wait on hold. You get transferred. You repeat yourself three times. You get a different answer depending on who picks up.

This felt like a genuine problem worth solving, not just a demo scenario. The EU insurance market handles over 1 billion customer contacts per year. Even a modest improvement in how those conversations go has real human impact.

---

## The Idea

I wanted to build something that could actually replace a Tier-1 insurance call — not just a chatbot that answers FAQs, but a system that listens to you, knows who you are, understands what you need, checks whether the answer is legally safe to give, and speaks back in your language.

That is a hard problem. Most "AI voice agents" I saw were either glorified IVR trees or demos that worked only in controlled conditions. I wanted to build something that would work in the messy real world.

The constraint I set myself: it had to work with free-tier APIs. If this could be built for near-zero cost, anyone could build it. If it required enterprise contracts, it was just a slide deck.

---

## What I Learned Building It

**Multi-agent architecture is harder than it looks.** The Router, Specialists, and ComplianceGuard seem obvious in the final diagram. They were not obvious at the start. The first version was a single Claude call that tried to do everything — route, answer, check compliance, detect escalation — in one prompt. It was unreliable and undebuggable. Splitting into agents made each piece testable and the whole system far more reliable.

**Compliance has to be code, not a comment.** My first approach was to write "always identify as AI" in the system prompt and hope Claude followed it. It mostly did. But "mostly" is not good enough for an EU AI Act requirement. Building ComplianceGuard as a separate agent that checks every reply before it is spoken — and can rewrite it — was the right call. It also made me think carefully about what compliance actually means in practice, which is more valuable than knowing the regulation by number.

**Voice is a different medium.** Everything I knew about building text chatbots was wrong for voice. Bullet points do not work. Long sentences do not work. Users do not re-read. If Tina says something confusing, the caller cannot scroll up. Every response had to be 2-3 sentences maximum, spoken naturally, with no markdown. This forced a kind of clarity that text chatbots do not require.

**Echo cancellation is a real engineering problem.** I spent an embarrassing amount of time debugging why Tina kept responding to her own voice. The browser mic picks up speaker output. The fix is `echoCancellation: true` in the Web Audio API — one line, but the path to finding it taught me how phone networks actually work.

**Deepgram struggles with non-native accents in a browser.** The most humbling part of the project. nova-3 is excellent over a clean phone line. Over a laptop microphone with background noise and a Russian accent speaking German, it produces creative transcriptions. Production voice agents run over telephony infrastructure for a reason. I documented this honestly rather than hiding it.

**n8n changed roles halfway through.** In the POC, n8n was the brain — it orchestrated everything. In the MVP, Python took over as the brain and n8n became the automation layer. Recognising that a tool can do different things in different phases, and being willing to restructure rather than force-fit the original architecture, was an important lesson.

---

## What I Would Do Differently

**Start with vector search, not keyword search.** My knowledge base uses keyword matching because I built it quickly. Real RAG uses semantic search — you embed the query and the documents and find similarity. I would use pgvector on Supabase from day one. It is free, it is already in the database, and the quality difference is significant.

**Build the evaluation framework first.** I built `evaluate.py` near the end. If I had built it at the start and run it after every change, I would have caught routing errors much earlier. Test-driven development for AI agents is not just good practice — it is the only way to know if your changes are actually improvements.

**Get a real phone number from day one.** The browser microphone was always going to be the weakest link. A Twilio phone number would have given real telephony audio from the start, made testing more realistic, and removed the echo cancellation problem entirely.

---

## What Surprised Me

I expected the AI reasoning to be the hard part. The agents, the prompts, the knowledge base — these were actually the most straightforward. Claude is very good at following instructions.

The hard parts were all infrastructure: WebSocket streaming, audio formats, event loop conflicts in Python 3.12 on Windows, Simli's WebRTC transport modes, OAuth token expiry in n8n at midnight. The boring parts that nobody writes blog posts about.

This is probably true of most real AI products. The AI is the easy part. The plumbing is the work.

---

## What I Am Most Proud Of

Not any single feature. The fact that it all works together.

A caller speaks. Tina hears them, identifies them from a database, understands what they need, checks the answer is safe to give, speaks back in their language, and if she cannot help, hands off to a human with a written briefing already prepared. In the background, n8n has already sent an email, logged the call, and alerted the team on Slack.

That is a real product, not a demo. It has gaps and limitations — I documented them honestly. But the core loop works. You can call it. It answers. That is what I came here to build.

---

*InsurVoice AI · github.com/dbystrova26/insurvoice-ai*
