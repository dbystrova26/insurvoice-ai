"""
server.py – InsurVoice AI backend
Threading async mode — works with gunicorn sync worker on Render.
6-second greeting delay so Simli is ready before audio plays.
/api/text uses the existing session agent via X-Socket-ID header.
"""

import os
import uuid
import time
import base64
import logging
import threading

import requests
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

from agent import InsurVoiceAgent
from stream import DeepgramStreamSession
from voice import synthesize_elevenlabs_mp3
from n8n_integration import fire_n8n_webhook
from crm import log_call_to_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET", "dev-secret")

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    transports=["websocket", "polling"],
    ping_timeout=60,
    ping_interval=25,
    logger=False,
    engineio_logger=False,
)

# ── Env vars ─────────────────────────────────────────────────────────────────
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
DEEPGRAM_KEY    = os.environ.get("DEEPGRAM_API_KEY", "")
ELEVENLABS_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
SIMLI_API_KEY   = os.environ.get("SIMLI_API_KEY", "")
SIMLI_FACE_ID   = os.environ.get("SIMLI_FACE_ID", "tmp9i8bbq7")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")
LLM_MODEL       = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")

# ── Per-socket state ──────────────────────────────────────────────────────────
sessions: dict[str, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_tts_mp3(text: str) -> str | None:
    try:
        mp3_bytes = synthesize_elevenlabs_mp3(text)
        return base64.b64encode(mp3_bytes).decode()
    except Exception as e:
        log.error("TTS error: %s", e)
        return None


def _maybe_fire_webhook(session: dict, result: dict, agent: InsurVoiceAgent):
    """
    Fire the n8n webhook for EVERY call turn, not just escalations.
    Also writes to Supabase call_log directly so the DB stays in sync
    with Google Sheets regardless of n8n availability.

    Guard: skip if this looks like a greeting escalation —
    no conversation history yet and intent is general_info.
    This handles the edge case where the greeting thread fires
    on a session that hit a transient error.
    """
    from n8n_integration import generate_call_summary, assess_urgency

    # Skip spurious escalations on the greeting turn:
    # real customer conversations always have at least 1 history entry
    intent    = result.get("intent", "")
    escalated = result.get("should_escalate", False)
    if escalated and not agent.conversation_history:
        log.info("[server] Suppressing escalation webhook — no conversation history (greeting error)")
        return

    route     = result.get("route", "")
    summary   = generate_call_summary(agent.conversation_history, route, not escalated)
    urgency   = assess_urgency(intent, session["turn_count"], result.get("handoff_summary", "") or "")

    # Write to Supabase call_log
    log_call_to_db({
        "call_id":          session["call_id"],
        "customer_id":      None,
        "language":         "en",
        "intent":           intent,
        "route":            route,
        "escalated":        escalated,
        "resolved":         not escalated,
        "turn_count":       session["turn_count"],
        "duration_seconds": 0,
        "compliance_passed": True,
        "urgency":          urgency,
        "summary":          summary,
        "handoff_summary":  result.get("handoff_summary", ""),
        "llm_used":         agent.model,
    })

    if not N8N_WEBHOOK_URL:
        return
    fire_n8n_webhook(
        call_id=session["call_id"],
        intent=intent,
        route=route,
        language="en",
        turn_count=session["turn_count"],
        resolved=not escalated,
        escalated=escalated,
        handoff_summary=result.get("handoff_summary", ""),
        compliance_passed=True,
        conversation_history=agent.conversation_history,
        llm_used=agent.model,
    )


def agent_and_tts(sid: str, text: str, is_greeting: bool = False):
    """
    Run the agent, synthesise TTS, emit reply over SocketIO.
    is_greeting=True for the synthetic server greeting — passed through
    to agent.respond() so it skips failure-counter tracking.  FIX [2].
    """
    session = sessions.get(sid)
    if not session:
        return
    agent = session["agent"]

    try:
        # FIX [2]: pass _is_greeting flag so the greeting turn doesn't
        # increment consecutive_failures and poison auto-escalation.
        result     = agent.respond(text, _is_greeting=is_greeting)
        reply_text = result["response"]
        audio_b64  = make_tts_mp3(reply_text)
        session["turn_count"] += 1

        socketio.emit("reply", {
            "reply":           reply_text,
            "intent":          result.get("intent", ""),
            "escalated":       result.get("should_escalate", False),
            "handoff_summary": result.get("handoff_summary", ""),
            "audio_base64":    audio_b64,
            "agent_trace":     [],
        }, to=sid)

        # FIX: skip webhook and call_log entirely for synthetic greeting turns.
        # The greeting is an internal prompt — it should never appear in logs,
        # never trigger n8n, and never escalate even if it hits an error.
        if not is_greeting:
            _maybe_fire_webhook(session, result, agent)
        elif result.get("should_escalate"):
            # Greeting escalated due to technical error — reset it silently
            log.warning("[%s] Greeting escalated (technical error) — suppressed", sid)
            result["should_escalate"] = False

    except Exception as e:
        import traceback
        logging.getLogger(__name__).error(
            "[server] agent_and_tts error for sid %s: %s\n%s",
            sid, e, traceback.format_exc())
        socketio.emit("reply", {
            "reply":        "I'm having a technical issue. Let me connect you to a colleague.",
            "intent":       "error",
            "escalated":    True,
            "audio_base64": None,
        }, to=sid)


# ── REST routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/avatar")
def avatar():
    return render_template("avatar.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status":     "ok",
        "anthropic":  bool(ANTHROPIC_KEY),
        "deepgram":   bool(DEEPGRAM_KEY),
        "elevenlabs": bool(ELEVENLABS_KEY),
        "simli":      bool(SIMLI_API_KEY),
    })


@app.route("/api/ping-db")
def ping_db():
    """
    Lightweight keep-alive endpoint for UptimeRobot (free plan).
    Hit this every 5 minutes to prevent Render instance sleep AND
    Supabase free-tier auto-pause (which triggers after 7 days inactivity).

    UptimeRobot setup:
      Monitor type: HTTP(s)
      URL: https://insurvoice-ai.onrender.com/api/ping-db
      Interval: 5 minutes
    """
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=5)
        conn.close()
        # Reset circuit breaker so RAG recovers immediately after a cold start
        from rag import _check_db_health
        _check_db_health()
        return jsonify({"status": "ok", "db": "reachable"})
    except Exception as e:
        return jsonify({"status": "ok", "db": "unreachable", "error": str(e)[:80]}), 200


@app.route("/api/simli/session")
def simli_session():
    if not SIMLI_API_KEY:
        return jsonify({"error": "SIMLI_API_KEY not configured"}), 503
    try:
        resp = requests.post(
            "https://api.simli.ai/startAudioToVideoSession",
            json={
                "faceId":    SIMLI_FACE_ID,
                "isJPG":     False,
                "apiKey":    SIMLI_API_KEY,
                "syncAudio": True,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return jsonify({
            "session_token": data.get("session_token") or data.get("token", ""),
            "ice_servers":   data.get("ice_servers", []),
            "livekit_url":   data.get("livekit_url", ""),
            "livekit_token": data.get("livekit_token", ""),
        })
    except Exception as e:
        log.error("Simli session error: %s", e)
        return jsonify({"error": str(e)}), 502


@app.route("/api/text", methods=["POST"])
def api_text():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty text"}), 400

    # Reuse existing session agent so conversation history is preserved
    sid = request.headers.get("X-Socket-ID", "")
    session = sessions.get(sid)
    if session:
        agent = session["agent"]
    else:
        agent = InsurVoiceAgent(api_key=ANTHROPIC_KEY, model=LLM_MODEL)

    result = agent.respond(text)
    reply_text = result["response"]

    audio_b64 = None
    if ELEVENLABS_KEY:
        audio_b64 = make_tts_mp3(reply_text)

    # FIX [5]: keep session turn_count in sync when text path reuses a session
    if session:
        session["turn_count"] += 1

    # FIX [4]: fire webhook for text-path turns too (escalated or not)
    if session:
        _maybe_fire_webhook(session, result, agent)

    return jsonify({
        "reply":           reply_text,
        "intent":          result.get("intent", ""),
        "escalated":       result.get("should_escalate", False),
        "handoff_summary": result.get("handoff_summary", ""),
        "audio_base64":    audio_b64,
        "agent_trace":     [],
    })


@app.route("/api/reset", methods=["POST"])
def api_reset():
    sid = request.headers.get("X-Socket-ID", "")
    # FIX [6]: warn clearly if the header is missing so it's not a silent no-op
    if not sid:
        log.warning("/api/reset called without X-Socket-ID header — nothing reset")
        return jsonify({"ok": False, "error": "X-Socket-ID header required"}), 400
    if sid not in sessions:
        log.warning("/api/reset: session %s not found", sid)
        return jsonify({"ok": False, "error": "session not found"}), 404
    sessions[sid]["agent"].reset()
    sessions[sid]["turn_count"] = 0
    sessions[sid]["call_id"]    = str(uuid.uuid4())
    return jsonify({"ok": True})


# ── Socket events ──────────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    sid = request.sid
    log.info("Client connected: %s", sid)

    sessions[sid] = {
        "agent":      InsurVoiceAgent(api_key=ANTHROPIC_KEY, model=LLM_MODEL),
        "dg_session": None,
        "call_id":    str(uuid.uuid4()),
        "turn_count": 0,
    }

    emit("connected", {
        "deepgram_available": bool(DEEPGRAM_KEY),
        "simli_api_key":      SIMLI_API_KEY,
        "simli_face_id":      SIMLI_FACE_ID,
    })

    # 6s delay so Simli has time to connect before greeting audio plays.
    # FIX [2]: pass is_greeting=True so the synthetic prompt does not count
    # toward the consecutive_failures auto-escalation threshold.
    def _delayed_greeting():
        time.sleep(6)
        if sid in sessions:
            agent_and_tts(sid, "Hello, please greet the customer.", is_greeting=True)

    threading.Thread(target=_delayed_greeting, daemon=True).start()


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    session = sessions.pop(sid, None)
    if session and session.get("dg_session"):
        try:
            session["dg_session"].stop()
        except Exception:
            pass
    log.info("Client disconnected: %s", sid)


@socketio.on("start_stream")
def on_start_stream():
    sid = request.sid
    session = sessions.get(sid)
    if not session:
        return

    def on_transcript(text: str, is_final: bool, language: str):
        if not is_final:
            socketio.emit("partial_transcript", {"text": text}, to=sid)
            return
        socketio.emit("transcript", {"text": text, "language": language}, to=sid)
        threading.Thread(target=agent_and_tts, args=(sid, text), daemon=True).start()

    dg = DeepgramStreamSession(api_key=DEEPGRAM_KEY, on_transcript=on_transcript)
    dg.start()
    session["dg_session"] = dg
    emit("stream_ready")


@socketio.on("stop_stream")
def on_stop_stream():
    sid = request.sid
    session = sessions.get(sid)
    if session and session.get("dg_session"):
        session["dg_session"].stop()
        session["dg_session"] = None


@socketio.on("resume_stream")
def on_resume_stream():
    on_start_stream()


@socketio.on("audio_chunk")
def on_audio_chunk(data):
    sid = request.sid
    session = sessions.get(sid)
    if not session:
        return
    dg = session.get("dg_session")
    if dg and dg.is_alive():
        if isinstance(data, (bytes, bytearray)):
            dg.send_audio(bytes(data))
        elif hasattr(data, "tobytes"):
            dg.send_audio(data.tobytes())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
