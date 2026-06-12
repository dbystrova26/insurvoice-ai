"""
server.py — InsurVoice AI · Flask + SocketIO server
-----------------------------------------------------
Serves the voice interface and runs the full pipeline server-side.

Two STT modes:
  LIVE  — Deepgram WebSocket streaming (phone-call feel, no button press)
  BATCH — Deepgram REST or Whisper (fallback for file uploads)

Pipeline per turn:
  Browser mic audio → Deepgram (live STT) → Router → Specialist → ComplianceGuard
  → ElevenLabs (TTS) → audio back to browser → plays automatically

Run locally:  python server.py
Deploy:       gunicorn with eventlet (see render.yaml)
"""

import os
import base64
import uuid
from flask import Flask, request, jsonify, render_template, session
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv

from agents import Orchestrator
from voice import synthesize_elevenlabs, DEFAULT_VOICE_ID
from stream import DeepgramStreamSession, transcribe_streaming_chunk

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "insurvoice-dev-change-in-prod")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY     = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
DEEPGRAM_KEY   = os.getenv("DEEPGRAM_API_KEY", "")
VOICE_ID       = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)

_agents: dict[str, Orchestrator] = {}
_streams: dict[str, DeepgramStreamSession] = {}


def _sid() -> str:
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def _get_agent(sid: str) -> Orchestrator:
    if sid not in _agents:
        _agents[sid] = Orchestrator(ANTHROPIC_KEY)
    return _agents[sid]


def _run_turn(sid: str, transcript: str, socket_id: str, language: str = "en"):
    """Run a full agent turn and emit the result back to the browser."""
    transcript = transcript.strip()
    if not transcript or len(transcript) < 4:
        return
    if transcript.lower() in {"the", "a", "uh", "um", "hmm", "oh", "ah"}:
        return
    socketio.emit("transcript", {"text": transcript, "language": language}, room=socket_id)
    agent = _get_agent(sid)
    # Pass detected language so agent replies in same language
    result = agent.respond(transcript, language=language)
    audio_b64 = None
    if ELEVENLABS_KEY:
        tts = synthesize_elevenlabs(result["response"], ELEVENLABS_KEY, VOICE_ID)
        if tts["success"]:
            audio_b64 = base64.b64encode(tts["audio"]).decode()
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
    socketio.emit("transcript", {"text": transcript}, room=socket_id)
    agent = _get_agent(sid)
    result = agent.respond(transcript)
    audio_b64 = None
    if ELEVENLABS_KEY:
        tts = synthesize_elevenlabs(result["response"], ELEVENLABS_KEY, VOICE_ID)
        if tts["success"]:
            audio_b64 = base64.b64encode(tts["audio"]).decode()
    socketio.emit("reply", {
        "transcript": transcript,
        "reply": result["response"],
        "intent": result.get("intent", ""),
        "route": result.get("route", ""),
        "escalated": result.get("should_escalate", False),
        "handoff_summary": result.get("handoff_summary"),
        "agent_trace": result.get("agent_trace", []),
        "compliance": result.get("compliance", {}),
        "audio_base64": audio_b64,
    }, room=socket_id)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "anthropic": bool(ANTHROPIC_KEY),
        "deepgram": bool(DEEPGRAM_KEY),
        "elevenlabs": bool(ELEVENLABS_KEY),
        "whisper_fallback": bool(OPENAI_KEY),
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    sid = _sid()
    if sid in _agents:
        _agents[sid].reset()
    return jsonify({"status": "reset"})


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
    result = agent.respond(stt["text"])
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


# ── SocketIO live streaming ───────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    join_room(request.sid)
    emit("connected", {
        "deepgram_available": bool(DEEPGRAM_KEY),
        "elevenlabs_available": bool(ELEVENLABS_KEY),
    })


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
