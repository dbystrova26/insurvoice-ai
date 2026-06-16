"""
server.py – InsurVoice AI backend
Threading async mode — works with gunicorn sync worker on Render.
No eventlet or gevent needed.
"""

import os
import uuid
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

# ── Env vars ────────────────────────────────────────────────────────────────
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
DEEPGRAM_KEY    = os.environ.get("DEEPGRAM_API_KEY", "")
ELEVENLABS_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
SIMLI_API_KEY   = os.environ.get("SIMLI_API_KEY", "")
SIMLI_FACE_ID   = os.environ.get("SIMLI_FACE_ID", "tmp9i8bbq7")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")

# ── Per-socket state ─────────────────────────────────────────────────────────
sessions: dict[str, dict] = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_tts_mp3(text: str) -> str | None:
    """Return base64-encoded MP3 or None on failure."""
    try:
        mp3_bytes = synthesize_elevenlabs_mp3(text)
        return base64.b64encode(mp3_bytes).decode()
    except Exception as e:
        log.error("TTS error: %s", e)
        return None


def agent_and_tts(sid: str, text: str):
    """Run agent + TTS in background thread, emit reply to client."""
    session = sessions.get(sid)
    if not session:
        return
    agent = session["agent"]

    try:
        result     = agent.respond(text)
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

        if N8N_WEBHOOK_URL and result.get("should_escalate"):
            fire_n8n_webhook(
                call_id=session["call_id"],
                intent=result.get("intent", ""),
                route=result.get("route", ""),
                language="en",
                turn_count=session["turn_count"],
                resolved=False,
                escalated=True,
                handoff_summary=result.get("handoff_summary", ""),
                compliance_passed=True,
                conversation_history=agent.conversation_history,
            )

    except Exception as e:
        log.error("[%s] agent_and_tts error: %s", sid, e)
        socketio.emit("reply", {
            "reply":        "I'm having a technical issue. Let me connect you to a colleague.",
            "intent":       "error",
            "escalated":    True,
            "audio_base64": None,
        }, to=sid)


# ── REST routes ──────────────────────────────────────────────────────────────

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


@app.route("/api/simli/session")
def simli_session():
    """Browser fetches this to get a Simli session token."""
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
    """Text-input fallback used by the Send button."""
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty text"}), 400

    agent  = InsurVoiceAgent(api_key=ANTHROPIC_KEY)
    result = agent.respond(text)
    reply_text = result["response"]

    audio_b64 = None
    if body.get("tts") and ELEVENLABS_KEY:
        audio_b64 = make_tts_mp3(reply_text)

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
    """Reset the agent conversation (New Call button)."""
    sid = request.headers.get("X-Socket-ID", "")
    if sid and sid in sessions:
        sessions[sid]["agent"].reset()
        sessions[sid]["turn_count"] = 0
        sessions[sid]["call_id"]    = str(uuid.uuid4())
    return jsonify({"ok": True})


# ── Socket events ─────────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    sid = request.sid
    log.info("Client connected: %s", sid)

    sessions[sid] = {
        "agent":      InsurVoiceAgent(api_key=ANTHROPIC_KEY),
        "dg_session": None,
        "call_id":    str(uuid.uuid4()),
        "turn_count": 0,
    }

    emit("connected", {
        "deepgram_available": bool(DEEPGRAM_KEY),
        "simli_api_key":      SIMLI_API_KEY,
        "simli_face_id":      SIMLI_FACE_ID,
    })

    # Send greeting in background thread
    threading.Thread(
        target=agent_and_tts,
        args=(sid, "Hello, please greet the customer."),
        daemon=True,
    ).start()


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
        threading.Thread(
            target=agent_and_tts,
            args=(sid, text),
            daemon=True,
        ).start()

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
    """Raw PCM16 from browser AudioWorklet → Deepgram."""
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
