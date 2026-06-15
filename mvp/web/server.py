"""
server.py — InsurVoice AI · Flask + SocketIO server
"""

import os
import base64
import uuid
import time
import requests as req
from flask import Flask, request, jsonify, render_template, session
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv

from agents import Orchestrator
from voice import synthesize_elevenlabs, DEFAULT_VOICE_ID
from stream import DeepgramStreamSession, transcribe_streaming_chunk
from n8n_integration import fire_n8n_webhook

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "insurvoice-dev-change-in-prod")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY     = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
DEEPGRAM_KEY   = os.getenv("DEEPGRAM_API_KEY", "")
VOICE_ID       = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
SIMLI_API_KEY  = os.getenv("SIMLI_API_KEY", "")
SIMLI_FACE_ID  = os.getenv("SIMLI_FACE_ID", "")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")

_agents: dict[str, Orchestrator] = {}
_streams: dict[str, DeepgramStreamSession] = {}
_last_turn: dict[str, tuple] = {}


def _sid() -> str:
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def _get_agent(sid: str) -> Orchestrator:
    if sid not in _agents:
        agent = Orchestrator(ANTHROPIC_KEY)
        agent.call_id = f"{sid[:8]}-{int(time.time())}"   # stable ID for this session
        _agents[sid] = agent
    return _agents[sid]


def _run_turn(sid: str, transcript: str, socket_id: str, language: str = "en"):
    transcript = transcript.strip()
    # Allow __greet__ trigger to pass through
    if transcript != "__greet__":
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

    audio_b64 = None
    if ELEVENLABS_KEY:
        tts = synthesize_elevenlabs(result["response"], ELEVENLABS_KEY, VOICE_ID)
        if tts["success"]:
            audio_b64 = base64.b64encode(tts["audio"]).decode()

    escalated = result.get("should_escalate", False)
    socketio.emit("reply", {
        "transcript": transcript,
        "reply": result["response"],
        "intent": result.get("intent", ""),
        "route": result.get("route", ""),
        "language": language,
        "escalated": escalated,
        "handoff_summary": result.get("handoff_summary"),
        "agent_trace": result.get("agent_trace", []),
        "compliance": result.get("compliance", {}),
        "audio_base64": audio_b64,
    }, room=socket_id)

    # Fire n8n webhook (non-blocking background thread)
    if N8N_WEBHOOK_URL:
        agent_obj = _get_agent(sid)
        fire_n8n_webhook(
            call_id=agent_obj.call_id,
            intent=result.get("intent", "unknown"),
            route=result.get("route", "general"),
            language=language,
            turn_count=getattr(agent_obj, "turn_count", 1),
            resolved=result.get("resolved", False),
            escalated=escalated,
            handoff_summary=result.get("handoff_summary", ""),
            compliance_passed=result.get("compliance", {}).get("compliant", True),
            conversation_history=getattr(agent_obj, "history", []),
            customer_name=agent_obj.customer.get("name") if agent_obj.customer else None,
            customer_email=agent_obj.customer.get("email") if agent_obj.customer else None,
        )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/avatar")
def avatar():
    return render_template("avatar.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "anthropic": bool(ANTHROPIC_KEY),
        "deepgram": bool(DEEPGRAM_KEY),
        "elevenlabs": bool(ELEVENLABS_KEY),
        "simli": bool(SIMLI_API_KEY),
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    sid = _sid()
    if sid in _agents:
        _agents[sid].reset()
    _last_turn.pop(sid, None)
    return jsonify({"status": "reset"})


@app.route("/api/simli/session")
def simli_session():
    if not SIMLI_API_KEY or not SIMLI_FACE_ID:
        return jsonify({"error": "Simli keys not configured"}), 500
    try:
        ice_resp = req.post(
            "https://api.simli.ai/getIceServers",
            headers={"Content-Type": "application/json"},
            json={"apiKey": SIMLI_API_KEY},
            timeout=10,
        )
        ice_servers = ice_resp.json() if ice_resp.status_code == 200 else None

        # Use compose/token endpoint for LiveKit transport
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
        if sess_resp.status_code != 200:
            # Fallback to old endpoint
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
            return jsonify({"error": f"Simli error: {sess_resp.text[:100]}"}), 502

        data = sess_resp.json()
        return jsonify({
            "session_token": data.get("session_token") or data.get("sessionToken"),
            "ice_servers": ice_servers,
        })
    except Exception as e:
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


@socketio.on("connect")
def on_connect():
    join_room(request.sid)
    emit("connected", {
        "deepgram_available": bool(DEEPGRAM_KEY),
        "elevenlabs_available": bool(ELEVENLABS_KEY),
        "simli_api_key": SIMLI_API_KEY,
        "simli_face_id": SIMLI_FACE_ID,
    })
    # Auto-greet — fire Tina's opening line immediately on connection
    import threading
    sid = _sid()
    socket_id = request.sid
    def _auto_greet():
        import time
        time.sleep(2)  # wait for Simli avatar to connect
        _run_turn(sid, "__greet__", socket_id, "en")
    threading.Thread(target=_auto_greet, daemon=True).start()


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
            import threading
            threading.Thread(
                target=_run_turn, args=(sid, text, socket_id, language), daemon=True
            ).start()
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
            import threading
            threading.Thread(
                target=_run_turn, args=(sid, text, socket_id, language), daemon=True
            ).start()
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
    if sid and sid in _streams:
        _streams[sid].stop()
        del _streams[sid]


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
