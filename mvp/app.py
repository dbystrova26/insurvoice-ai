"""
app.py — InsurVoice AI · Voice Agent MVP
------------------------------------------
A Parloa-style AI voice agent for insurance customer service.

Pipeline:  Microphone / file → Whisper (STT) → Claude (agent) → ElevenLabs (TTS) → audio playback

Run locally:  streamlit run app.py
Deploy:       see render.yaml / mvp_documentation.md
"""

import os
import base64
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from voice import transcribe_whisper, synthesize_elevenlabs, list_elevenlabs_voices, DEFAULT_VOICE_ID

load_dotenv()

st.set_page_config(page_title="InsurVoice AI", page_icon="🎙️",
                   layout="wide", initial_sidebar_state="expanded")

# Try to import the mic recorder component (graceful fallback if unavailable)
try:
    from streamlit_mic_recorder import mic_recorder
    MIC_AVAILABLE = True
except ImportError:
    MIC_AVAILABLE = False

st.markdown("""
<style>
  .user-bubble{background:#1a3c5e;color:#fff;padding:10px 16px;border-radius:18px 18px 4px 18px;margin:6px 0 6px 18%;font-size:14px;line-height:1.5}
  .bot-bubble{background:#f0f4f8;color:#1a1a2e;padding:10px 16px;border-radius:18px 18px 18px 4px;margin:6px 18% 6px 0;font-size:14px;line-height:1.5;border:1px solid #dce5f0}
  .escalation-bubble{background:#fff3cd;color:#856404;padding:10px 16px;border-radius:8px;margin:6px 0;font-size:13px;border:1px solid #ffc107}
  .ai-badge{background:#e8f4fd;color:#1a3c5e;font-size:11px;padding:2px 8px;border-radius:10px;margin-bottom:4px;display:inline-block}
  .intent-tag{background:#e9ecef;color:#495057;font-size:10px;padding:1px 6px;border-radius:8px;margin-left:6px}
  .pipeline-step{display:inline-block;background:#f7f9fc;border:1px solid #dce5f0;border-radius:6px;padding:4px 10px;margin:2px;font-size:11px;color:#1a3c5e}
  .voice-status{background:#e8f4fd;border-left:4px solid #1a3c5e;padding:8px 14px;border-radius:4px;font-size:13px;margin:6px 0}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "escalated" not in st.session_state:
    st.session_state.escalated = False
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None
if "stats" not in st.session_state:
    st.session_state.stats = {"total": 0, "resolved_by_ai": 0, "escalated": 0, "intents": {}}


def autoplay_audio(audio_bytes: bytes):
    """Embed audio that plays automatically in the browser."""
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f'<audio autoplay controls style="width:100%;margin-top:6px">'
        f'<source src="data:audio/mp3;base64,{b64}" type="audio/mpeg"></audio>',
        unsafe_allow_html=True,
    )


def process_turn(user_text, anthropic_key, eleven_key, voice_id, tts_enabled):
    """Run one full conversation turn: agent → optional TTS."""
    # Init agent
    if st.session_state.agent is None:
        from agent import InsurVoiceAgent
        st.session_state.agent = InsurVoiceAgent(anthropic_key)

    st.session_state.messages.append({"role": "user", "text": user_text, "ts": datetime.now().isoformat()})
    st.session_state.stats["total"] += 1

    with st.spinner("InsurVoice is thinking..."):
        result = st.session_state.agent.respond(user_text)

    bot_audio = None
    if tts_enabled and eleven_key:
        with st.spinner("Generating voice response..."):
            tts = synthesize_elevenlabs(result["response"], eleven_key, voice_id)
            if tts["success"]:
                bot_audio = tts["audio"]
            else:
                st.warning(f"Voice synthesis: {tts['error']} (showing text only)")

    st.session_state.messages.append({
        "role": "bot",
        "text": result["response"],
        "intent": result.get("intent", ""),
        "confidence": result.get("confidence", 0),
        "audio": bot_audio,
        "ts": datetime.now().isoformat(),
    })

    intent = result.get("intent", "unknown")
    st.session_state.stats["intents"][intent] = st.session_state.stats["intents"].get(intent, 0) + 1

    if result.get("should_escalate"):
        st.session_state.escalated = True
        st.session_state.stats["escalated"] += 1
        summary = result.get("handoff_summary", "")
        st.session_state.messages.append({
            "role": "escalation",
            "text": f"Transferring to a human colleague. Reference: {datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    + (f"<br><small><b>Agent briefing:</b> {summary}</small>" if summary else ""),
            "ts": datetime.now().isoformat(),
        })
    else:
        st.session_state.stats["resolved_by_ai"] += 1


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎙️ InsurVoice AI")
    st.caption("AI Voice Agent for Insurance · Parloa-style POC")
    st.caption("Ironhack AI Consulting Bootcamp")
    st.divider()

    st.markdown("**API keys**")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "") or st.text_input(
        "Anthropic API key", type="password", help="console.anthropic.com")
    openai_key = os.getenv("OPENAI_API_KEY", "") or st.text_input(
        "OpenAI API key (Whisper STT)", type="password", help="platform.openai.com — for speech-to-text")
    eleven_key = os.getenv("ELEVENLABS_API_KEY", "") or st.text_input(
        "ElevenLabs API key (TTS)", type="password", help="elevenlabs.io — for voice output")

    st.divider()
    tts_enabled = st.toggle("🔊 Voice responses (TTS)", value=True,
                            help="Turn off to get text-only replies and save ElevenLabs quota")

    voice_id = DEFAULT_VOICE_ID
    if eleven_key and tts_enabled:
        voices = list_elevenlabs_voices(eleven_key)
        voice_names = {v["name"]: v["id"] for v in voices}
        chosen = st.selectbox("Voice", list(voice_names.keys()))
        voice_id = voice_names[chosen]

    st.divider()
    if st.button("🔄 New call", use_container_width=True):
        st.session_state.messages = []
        st.session_state.escalated = False
        st.session_state.last_audio_hash = None
        if st.session_state.agent:
            st.session_state.agent.reset()
        st.rerun()

    st.divider()
    st.caption("**Pipeline:** Mic/file → Whisper → Claude → ElevenLabs → audio")
    st.caption("EU AI Act Art. 52: AI identity disclosed on first turn.")
    st.caption("GDPR: audio processed in-session, not stored.")


# ── Main tabs ─────────────────────────────────────────────────────────────────
tab_call, tab_monitor, tab_about = st.tabs(["🎙️ Voice Call", "📊 Monitoring", "ℹ️ How it works"])

with tab_call:
    st.markdown("## InsurVoice AI — Live Voice Agent")
    st.caption("Speak or upload audio. The AI transcribes, answers, and replies in voice — like Parloa.")

    # Render conversation
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="user-bubble">🗣️ {msg["text"]}</div>', unsafe_allow_html=True)
        elif msg["role"] == "bot":
            tag = f'<span class="intent-tag">{msg.get("intent","")}</span>' if msg.get("intent") else ""
            st.markdown(f'<div class="ai-badge">🤖 InsurVoice AI</div>{tag}'
                        f'<div class="bot-bubble">{msg["text"]}</div>', unsafe_allow_html=True)
            if msg.get("audio"):
                autoplay_audio(msg["audio"])
        elif msg["role"] == "escalation":
            st.markdown(f'<div class="escalation-bubble">⚡ <b>Escalated to human colleague</b><br>'
                        f'<small>{msg["text"]}</small></div>', unsafe_allow_html=True)

    st.divider()

    if st.session_state.escalated:
        st.info("✅ Call transferred to a human colleague. This AI session has ended.")
        if st.button("Start new call"):
            st.session_state.messages = []
            st.session_state.escalated = False
            if st.session_state.agent:
                st.session_state.agent.reset()
            st.rerun()
    else:
        if not anthropic_key:
            st.warning("Enter your Anthropic API key in the sidebar to start.")
        else:
            col1, col2 = st.columns([1, 1])

            # ── Primary: microphone ──
            with col1:
                st.markdown("**🎤 Speak (primary)**")
                if MIC_AVAILABLE:
                    audio = mic_recorder(start_prompt="🔴 Start speaking",
                                         stop_prompt="⏹️ Stop",
                                         key="mic", format="wav")
                    if audio and audio.get("bytes"):
                        audio_hash = hash(audio["bytes"][:200])
                        if audio_hash != st.session_state.last_audio_hash:
                            st.session_state.last_audio_hash = audio_hash
                            if not openai_key:
                                st.error("OpenAI API key needed for speech-to-text.")
                            else:
                                with st.spinner("Transcribing..."):
                                    stt = transcribe_whisper(audio["bytes"], openai_key, "mic.wav")
                                if stt["success"]:
                                    process_turn(stt["text"], anthropic_key, eleven_key, voice_id, tts_enabled)
                                    st.rerun()
                                else:
                                    st.error(f"Transcription: {stt['error']}")
                else:
                    st.info("Mic component not installed. Use file upload or text below.")

            # ── Fallback: file upload ──
            with col2:
                st.markdown("**📁 Upload audio (fallback)**")
                up = st.file_uploader("WAV / MP3 / M4A", type=["wav", "mp3", "m4a", "webm"],
                                      label_visibility="collapsed")
                if up is not None:
                    audio_bytes = up.read()
                    audio_hash = hash(audio_bytes[:200])
                    if audio_hash != st.session_state.last_audio_hash:
                        st.session_state.last_audio_hash = audio_hash
                        if not openai_key:
                            st.error("OpenAI API key needed for speech-to-text.")
                        else:
                            with st.spinner("Transcribing..."):
                                stt = transcribe_whisper(audio_bytes, openai_key, up.name)
                            if stt["success"]:
                                process_turn(stt["text"], anthropic_key, eleven_key, voice_id, tts_enabled)
                                st.rerun()
                            else:
                                st.error(f"Transcription: {stt['error']}")

            # ── Text fallback (always works) ──
            st.markdown("**⌨️ Or type (always available)**")
            typed = st.chat_input("Type your question...")
            if typed:
                process_turn(typed, anthropic_key, eleven_key, voice_id, tts_enabled)
                st.rerun()


with tab_monitor:
    st.markdown("## Call Monitoring Dashboard")
    s = st.session_state.stats
    total, resolved, esc = s["total"], s["resolved_by_ai"], s["escalated"]
    deflection = (resolved / total * 100) if total else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total turns", total)
    c2.metric("AI resolved", resolved)
    c3.metric("Escalated", esc)
    c4.metric("Deflection rate", f"{deflection:.0f}%", delta="Target 60%" if deflection < 60 else "✓")

    st.divider()
    st.markdown("**Intent distribution**")
    if s["intents"]:
        import pandas as pd
        df = pd.DataFrame([(k, v) for k, v in s["intents"].items()], columns=["Intent", "Count"])
        st.bar_chart(df.set_index("Intent"))
    else:
        st.caption("No calls yet.")


with tab_about:
    st.markdown("## How InsurVoice AI works")
    st.markdown("""
    InsurVoice is a **voice-first AI agent** in the same product category as
    [Parloa](https://parloa.com) — it answers insurance customer calls autonomously
    and hands off to a human when needed.

    **The voice pipeline:**
    """)
    st.markdown("""
    <div>
      <span class="pipeline-step">1. 🎤 Customer speaks (mic or upload)</span>
      <span class="pipeline-step">2. 📝 Whisper transcribes to text</span>
      <span class="pipeline-step">3. 🧠 Claude classifies intent + generates reply</span>
      <span class="pipeline-step">4. 🔊 ElevenLabs speaks the reply</span>
      <span class="pipeline-step">5. ↪️ Escalates to human if needed</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    **Tech stack:**
    - **Speech-to-text:** OpenAI Whisper (`whisper-1`)
    - **Reasoning:** Anthropic Claude `claude-opus-4-6`
    - **Text-to-speech:** ElevenLabs (`eleven_turbo_v2_5`)
    - **Knowledge:** RAG over insurance FAQ knowledge base
    - **Frontend:** Streamlit, deployable to Render

    **Compliance:**
    - EU AI Act **Limited Risk** (Art. 52) — AI identity disclosed at call start
    - GDPR — audio processed in-session, never stored; voice is biometric-adjacent so
      retention policy and DPIA apply (see compliance docs)

    **Why this matters vs the chat version:** voice is Parloa's actual product.
    A voice demo shows the full STT → reasoning → TTS loop that defines the category.
    """)
