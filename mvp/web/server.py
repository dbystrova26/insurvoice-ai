"""
server.py — InsurVoice AI · Flask + SocketIO server
Feature/simli-avatar branch logic + Render deployment fixes
"""

# ✅ CRITICAL: Gevent monkey patch MUST be first (required for Render/gunicorn)
from gevent import monkey
monkey.patch_all()

import os
import base64
import uuid
import time
import requests as req
import logging
from flask import Flask, request, jsonify, render_template, session
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv

from agents import Orchestrator
from voice import synthesize_elevenlabs, DEFAULT_VOICE_ID
from stream import DeepgramStreamSession, transcribe_streaming_chunk
from n8n_integration import fire_n8n_webhook

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "insurvoice-dev-change-in-prod")

# ✅ gevent async_mode + polling only (Render free tier has no WebSocket support)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="gevent",
    transports=["polling"],
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=10_000_000,  # allow larger audio payloads
)

ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY     = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
DEEPGRAM_KEY   = os.getenv("DEEPGRAM_API_KEY", "")
VOICE_ID       = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
SIMLI_API_KEY  = os.getenv("SIMLI_API_KEY", "")
SIMLI_FACE_ID  = os.getenv("SIMLI_FACE_ID", "")

_agents: dict[str, Orchestrator] = {}
_streams: dict[str, DeepgramStreamSession] = {}
_last_turn: dict[str, tuple] = {}
_call_meta: dict[str, dict] = {}


def _sid() -> str:
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def _get_agent(sid: str) -> Orchestrator:
    if sid not in _agents:
        _agents[sid] = Orchestrator(ANTHROPIC_KEY)
        _call_meta[sid] = {
            "call_id": uuid.uuid4().hex,
            "start_time": time.time(),
            "turns": 0,
            "escalated": False,
        }
    return _agents[sid]


def _run_turn(sid: str, transcript: str, socket_id: str, language: str = "en"):
    transcript = transcript.strip()
    if not transcript or len(transcript) < 4:
        return
    if transcript.lower() in {"the", "a", "uh", "um", "hmm", "oh", "ah"}:
        return

    now = time.time()
    last_text, last_time = _last_turn.get(sid, ("", 0))
    if (now - last_time) < 4.0:
        if transcript == last_text:
            return
        if transcript.lower() in last_text.lower() or last_text.lower() in transcript.lower():
            return
    _last_turn[sid] = (transcript, now)

    socketio.emit("transcript", {"text": transcript, "language": language}, room=socket_id)

    agent = _get_agent(sid)
    result = agent.respond(transcript, language=language)

    # Track metadata for n8n
    if sid in _call_meta:
        _call_meta[sid]["turns"] += 1
        _call_meta[sid]["escalated"] = result.get("should_escalate", False)

    audio_b64 = None
    if ELEVENLABS_KEY:
        tts = synthesize_elevenlabs(result["response"], ELEVENLABS_KEY, VOICE_ID)
        if tts["success"]:
            audio_b64 = base64.b64encode(tts["audio"]).decode()
            logger.info(f"[TTS] Generated {len(tts['audio'])} bytes")

    socketio.emit("reply", {
        "transcript": transcript,
        "reply": result["response"],
        "intent": result.get("intent", ""),
        "route": result.get("route", ""),
        "language": language,
        "escalated": result.get("should_escalate", False),
        "handoff_summary": result.get("handoff_summary"),
        "agent_trace": result.get("agent_trace", []),
        "compliance": result.get("compliance", {}),
        "audio_base64": audio_b64,
    }, room=socket_id)


# ── HTTP Routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/avatar")
def avatar():
    # Inject Simli credentials so avatar.html can use them
    return render_template(
        "avatar.html",
        simli_api_key=SIMLI_API_KEY,
        simli_face_id=SIMLI_FACE_ID,
    )


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "anthropic": bool(ANTHROPIC_KEY),
        "deepgram": bool(DEEPGRAM_KEY),
        "elevenlabs": bool(ELEVENLABS_KEY),
        "simli": bool(SIMLI_API_KEY and SIMLI_FACE_ID),
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    sid = _sid()
    if sid in _agents:
        _agents[sid].reset()
    if sid in _streams:
        _streams[sid].stop()
        del _streams[sid]
    _last_turn.pop(sid, None)
    return jsonify({"status": "reset"})


@app.route("/api/simli/session")
def simli_session():
    if not SIMLI_API_KEY or not SIMLI_FACE_ID:
        return jsonify({"error": "Simli keys not configured"}), 500
    try:
        # Fetch ICE servers from Simli
        ice_servers = None
        try:
            ice_resp = req.post(
                "https://api.simli.ai/getIceServers",
                headers={"Content-Type": "application/json"},
                json={"apiKey": SIMLI_API_KEY},
                timeout=10,
            )
            if ice_resp.status_code == 200:
                ice_servers = ice_resp.json()
        except Exception as e:
            logger.warning(f"[Simli] ICE server fetch failed: {e}")

        # Get session token via compose/token (primary)
        sess_resp = req.post(
            "https://api.simli.ai/compose/token",
            headers={"Content-Type": "application/json"},
            json={
                "faceId": SIMLI_FACE_ID,
                "apiKey": SIMLI_API_KEY,
                "handleSilence": True,
                "maxSessionLength": 600,
                "maxIdleTime": 180,
            },
            timeout=10,
        )

        # Fallback to legacy endpoint if compose/token fails
        if sess_resp.status_code != 200:
            logger.warning(f"[Simli] compose/token failed ({sess_resp.status_code}), trying legacy")
            sess_resp = req.post(
                "https://api.simli.ai/startAudioToVideoSession",
                headers={"Content-Type": "application/json"},
                json={
                    "faceId": SIMLI_FACE_ID,
                    "isJPG": False,
                    "apiKey": SIMLI_API_KEY,
                    "handleSilence": True,
                    "maxSessionLength": 600,
                    "maxIdleTime": 180,
                },
                timeout=10,
            )

        if sess_resp.status_code != 200:
            logger.error(f"[Simli] Session error: {sess_resp.status_code} {sess_resp.text[:100]}")
            return jsonify({"error": f"Simli error: {sess_resp.text[:100]}"}), 502

        data = sess_resp.json()
        session_token = data.get("session_token") or data.get("sessionToken")
        logger.info("[Simli] Session token obtained")

        return jsonify({
            "session_token": session_token,
            "ice_servers": ice_servers,
        })

    except Exception as e:
        logger.error(f"[Simli] Exception: {e}")
        return jsonify({"error": str(e)[:100]}), 500


@app.route("/api/text", methods=["POST"])
def handle_text():
    if not ANTHROPIC_KEY:
        return jsonify({"error": "Missing ANTHROPIC_API_KEY"}), 500
    data = request.get_json(force=True)
    user_text = (data.get("text") or "").strip()
    if not user_text:
        return jsonify({"error": "Empty message"}), 400
    agent = _get_agent(_sid())
    result = agent.respond(user_text)
    audio_b64 = None
    if ELEVENLABS_KEY and data.get("tts", True):
        tts = synthesize_elevenlabs(result["response"], ELEVENLABS_KEY, VOICE_ID)
        if tts["success"]:
            audio_b64 = base64.b64encode(tts["audio"]).decode()
    return jsonify({
        "transcript": user_text,
        "reply": result["response"],
        "intent": result.get("intent", ""),
        "route": result.get("route", ""),
        "escalated": result.get("should_escalate", False),
        "handoff_summary": result.get("handoff_summary"),
        "agent_trace": result.get("agent_trace", []),
        "compliance": result.get("compliance", {}),
        "audio_base64": audio_b64,
    })


@app.route("/api/upload", methods=["POST"])
def handle_upload():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400
    audio_bytes = request.files["audio"].read()
    filename = request.files["audio"].filename or "upload.webm"
    if DEEPGRAM_KEY:
        stt = transcribe_streaming_chunk(audio_bytes, DEEPGRAM_KEY)
    elif OPENAI_KEY:
        from voice import transcribe_whisper
        stt = transcribe_whisper(audio_bytes, OPENAI_KEY, filename)
    else:
        return jsonify({"error": "No STT key configured"}), 500
    if not stt["success"]:
        return jsonify({"error": stt["error"]}), 502
    agent = _get_agent(_sid())
    lang = stt.get("language", "en")
    result = agent.respond(stt["text"], language=lang)
    audio_b64 = None
    if ELEVENLABS_KEY:
        tts = synthesize_elevenlabs(result["response"], ELEVENLABS_KEY, VOICE_ID)
        if tts["success"]:
            audio_b64 = base64.b64encode(tts["audio"]).decode()
    return jsonify({
        "transcript": stt["text"],
        "reply": result["response"],
        "intent": result.get("intent", ""),
        "route": result.get("route", ""),
        "escalated": result.get("should_escalate", False),
        "handoff_summary": result.get("handoff_summary"),
        "agent_trace": result.get("agent_trace", []),
        "compliance": result.get("compliance", {}),
        "audio_base64": audio_b64,
    })


# ── SocketIO Events ─────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    join_room(request.sid)
    sid = _sid()
    socket_id = request.sid
    emit("connected", {
        "deepgram_available": bool(DEEPGRAM_KEY),
        "elevenlabs_available": bool(ELEVENLABS_KEY),
        "simli_api_key": SIMLI_API_KEY,
        "simli_face_id": SIMLI_FACE_ID,
    })
    # Auto-greeting once the client connects
    socketio.start_background_task(_send_greeting, sid, socket_id)


def _send_greeting(sid: str, socket_id: str):
    """Send the opening greeting with TTS audio."""
    greeting = ("Hello, you're speaking with InsurVoice, an AI assistant for "
                "Allianz Direct. How can I help you today?")
    audio_b64 = None
    if ELEVENLABS_KEY:
        tts = synthesize_elevenlabs(greeting, ELEVENLABS_KEY, VOICE_ID)
        if tts["success"]:
            audio_b64 = base64.b64encode(tts["audio"]).decode()
    socketio.emit("reply", {
        "transcript": "",
        "reply": greeting,
        "intent": "greeting",
        "route": "orchestrator",
        "language": "en",
        "escalated": False,
        "handoff_summary": None,
        "agent_trace": [],
        "compliance": {},
        "audio_base64": audio_b64,
    }, room=socket_id)


@socketio.on("start_stream")
def on_start_stream():
    if not DEEPGRAM_KEY:
        emit("stream_error", {"error": "No DEEPGRAM_API_KEY on server"})
        return
    socket_id = request.sid
    sid = _sid()
    if sid in _streams:
        _streams[sid].stop()

    def on_transcript(text: str, is_final: bool, language: str = "en"):
        if is_final:
            # ✅ Use socketio.start_background_task (gevent-safe, not threading.Thread)
            socketio.start_background_task(_run_turn, sid, text, socket_id, language)
        else:
            socketio.emit("partial_transcript", {"text": text}, room=socket_id)

    stream = DeepgramStreamSession(DEEPGRAM_KEY, on_transcript)
    stream.start()
    _streams[sid] = stream
    emit("stream_ready", {"status": "listening"})


@socketio.on("audio_chunk")
def on_audio_chunk(data):
    sid = _sid()
    if sid in _streams:
        chunk = data if isinstance(data, bytes) else bytes(data)
        _streams[sid].send_audio(chunk)


@socketio.on("resume_stream")
def on_resume_stream():
    sid = _sid()
    if sid in _streams and _streams[sid].is_alive():
        return
    if not DEEPGRAM_KEY:
        return
    socket_id = request.sid

    def on_transcript(text: str, is_final: bool, language: str = "en"):
        if is_final:
            socketio.start_background_task(_run_turn, sid, text, socket_id, language)
        else:
            socketio.emit("partial_transcript", {"text": text}, room=socket_id)

    stream = DeepgramStreamSession(DEEPGRAM_KEY, on_transcript)
    stream.start()
    _streams[sid] = stream


@socketio.on("stop_stream")
def on_stop_stream():
    sid = _sid()
    if sid in _streams:
        _streams[sid].stop()
        del _streams[sid]


@socketio.on("disconnect")
def on_disconnect():
    sid = session.get("sid")
    if not sid:
        return
    if sid in _streams:
        _streams[sid].stop()
        del _streams[sid]

    # Fire n8n webhook on disconnect
    if sid in _call_meta:
        meta = _call_meta[sid]
        fire_n8n_webhook(
            call_id=meta["call_id"],
            intent="general",
            route="general",
            language="en",
            turn_count=meta["turns"],
            resolved=not meta["escalated"],
            escalated=meta["escalated"],
            handoff_summary="",
            compliance_passed=True,
            conversation_history=[],
            duration_seconds=int(time.time() - meta["start_time"]),
        )
        del _call_meta[sid]

    if sid in _agents:
        del _agents[sid]


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    logger.info(f"Starting InsurVoice AI on port {port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=False, log_output=True)
