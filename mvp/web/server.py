"""
server.py — InsurVoice AI · Flask + SocketIO server
Complete production-ready version with all fixes
"""

# ✅ CRITICAL: Gevent monkey patch MUST be first
from gevent import monkey
monkey.patch_all()

import os
import uuid
import time
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session, Response
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv
import logging

# Import agent, voice, and stream modules
from agent import InsurVoiceAgent
from voice import synthesize_elevenlabs, DEFAULT_VOICE_ID
from stream import DeepgramStreamSession
from crm import find_customer, format_customer_context, log_call_to_db
from n8n_integration import fire_n8n_webhook

load_dotenv()

# ── Setup ──────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "insurvoice-dev-change-in-prod")

# ✅ SocketIO with gevent async mode + polling transport (Render-safe)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="gevent",
    transports=["polling"],  # Render free tier doesn't support WebSocket
    ping_timeout=60,
    ping_interval=25,
)

# API Keys
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
DEEPGRAM_KEY   = os.getenv("DEEPGRAM_API_KEY", "")
VOICE_ID       = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
SIMLI_API_KEY  = os.getenv("SIMLI_API_KEY", "")
SIMLI_FACE_ID  = os.getenv("SIMLI_FACE_ID", "")

# State management
_agents: dict[str, InsurVoiceAgent] = {}
_streams: dict[str, DeepgramStreamSession] = {}
_audio_cache: dict[str, bytes] = {}  # ✅ Global cache for audio files
_call_meta: dict[str, dict] = {}  # Track call metadata (for n8n logging)
_last_turn: dict[str, tuple] = {}  # Dedup protection

logger = logging.getLogger(__name__)


# ── Utilities ──────────────────────────────────────────────────────────────

def _sid() -> str:
    """Get or create session ID."""
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def _get_agent(sid: str) -> InsurVoiceAgent:
    """Get or create agent for this session."""
    if sid not in _agents:
        _agents[sid] = InsurVoiceAgent(ANTHROPIC_KEY)
        _call_meta[sid] = {
            "call_id": uuid.uuid4().hex,
            "start_time": time.time(),
            "turns": 0,
            "escalated": False,
            "customer": None,
        }
    return _agents[sid]


def _run_turn(sid: str, transcript: str, socket_id: str, language: str = "en"):
    """
    Process a turn: transcribed text → agent → TTS → emit reply.
    Runs in background thread (gevent task).
    """
    transcript = transcript.strip()
    
    # ✅ Skip greet on first turn (handled by __greet__ special case)
    if transcript == "__greet__":
        # Send greeting without storing in history
        socketio.emit("reply", {
            "transcript": "",
            "reply": "Hello, you're speaking with InsurVoice, an AI assistant for Allianz Direct. How can I help you today?",
            "intent": "greeting",
            "route": "orchestrator",
            "language": language,
            "escalated": False,
            "handoff_summary": None,
            "audio_url": None,
            "compliance": {"passed": True, "note": "AI disclosure on first turn"},
        }, room=socket_id)
        return
    
    # Skip empty/junk input
    if not transcript or len(transcript) < 4:
        return
    if transcript.lower() in {"the", "a", "uh", "um", "hmm", "oh", "ah"}:
        return
    
    # ✅ Dedup protection: don't repeat same text within 4 seconds
    now = time.time()
    last_text, last_time = _last_turn.get(sid, ("", 0))
    if (now - last_time) < 4.0:
        if transcript == last_text:
            return
        if transcript.lower() in last_text.lower() or last_text.lower() in transcript.lower():
            return
    _last_turn[sid] = (transcript, now)

    # Emit back what we heard (for UX clarity)
    socketio.emit("transcript", {"text": transcript, "language": language}, room=socket_id)

    # Get agent and process
    agent = _get_agent(sid)
    result = agent.respond(transcript)

    # Update call metadata
    if sid in _call_meta:
        _call_meta[sid]["turns"] += 1
        _call_meta[sid]["escalated"] = result.get("should_escalate", False)

    # ✅ Generate TTS audio
    audio_url = None
    if ELEVENLABS_KEY and result.get("response"):
        tts_result = synthesize_elevenlabs(result["response"], ELEVENLABS_KEY, VOICE_ID)
        if tts_result["success"]:
            audio_id = str(uuid.uuid4())
            _audio_cache[audio_id] = tts_result["audio"]  # Store bytes (not base64)
            audio_url = f"/api/audio/{audio_id}"  # ✅ Send URL to client
            logger.info(f"[TTS] Generated {audio_id}: {len(tts_result['audio'])} bytes")
        else:
            logger.warning(f"[TTS] Failed: {tts_result['error']}")

    # ✅ Emit reply with audio URL (not base64)
    socketio.emit("reply", {
        "transcript": transcript,
        "reply": result["response"],
        "intent": result.get("intent", "general_info"),
        "route": result.get("route", "general"),
        "language": language,
        "escalated": result.get("should_escalate", False),
        "handoff_summary": result.get("handoff_summary"),
        "audio_url": audio_url,  # ✅ URL, not data
    }, room=socket_id)

    logger.info(f"[Turn] sid={sid[:8]} intent={result.get('intent')} escalated={result.get('should_escalate')}")


# ── HTTP Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/avatar")
def avatar():
    """Serve avatar page, injecting Simli credentials."""
    return render_template(
        "avatar.html",
        simli_api_key=SIMLI_API_KEY,
        simli_face_id=SIMLI_FACE_ID,
    )


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "anthropic": bool(ANTHROPIC_KEY),
        "deepgram": bool(DEEPGRAM_KEY),
        "elevenlabs": bool(ELEVENLABS_KEY),
        "simli": bool(SIMLI_API_KEY and SIMLI_FACE_ID),
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    """Reset the call (clear agent history, restart stream)."""
    sid = _sid()
    if sid in _agents:
        _agents[sid].reset()
    if sid in _streams:
        _streams[sid].stop()
        del _streams[sid]
    _last_turn.pop(sid, None)
    return jsonify({"status": "reset"})


@app.route("/api/audio/<audio_id>")
def serve_audio(audio_id):
    """
    ✅ CRITICAL FIX: Serve cached audio as binary MP3.
    
    Called by browser: <audio src="/api/audio/abc123">
    Returns binary audio bytes with correct headers.
    """
    # Retrieve (and remove) audio from cache
    audio_bytes = _audio_cache.pop(audio_id, None)
    
    if not audio_bytes:
        logger.warning(f"[Audio] Cache miss: {audio_id}")
        return "", 404
    
    # ✅ Return as binary MP3 stream (not JSON, not base64)
    response = Response(audio_bytes, mimetype="audio/mpeg")
    response.headers["Content-Type"] = "audio/mpeg"
    response.headers["Content-Length"] = len(audio_bytes)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cache-Control"] = "public, max-age=3600"
    
    logger.info(f"[Audio] Served {audio_id}: {len(audio_bytes)} bytes")
    return response


@app.route("/api/simli/session")
def simli_session():
    """
    ✅ Get Simli WebRTC session token for avatar video streaming.
    
    Called by frontend to initialize LiveKit connection for avatar.
    Returns session token + ICE servers.
    """
    if not SIMLI_API_KEY or not SIMLI_FACE_ID:
        logger.warning("[Simli] Keys not configured")
        return jsonify({"error": "Simli keys not configured"}), 500
    
    try:
        import requests as req
        
        # Get ICE servers (optional)
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
        
        # Get session token (try new endpoint first, fallback to old)
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
            logger.warning("[Simli] New endpoint failed, trying legacy endpoint")
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
        
        logger.info(f"[Simli] Session created successfully")
        
        return jsonify({
            "session_token": data.get("session_token") or data.get("sessionToken"),
            "ice_servers": ice_servers,
        })
    
    except Exception as e:
        logger.error(f"[Simli] Exception: {str(e)[:100]}")
        return jsonify({"error": str(e)[:100]}), 500


@app.route("/api/text", methods=["POST"])
def handle_text():
    """
    Handle text input (no voice).
    Used for fallback when microphone is not available.
    """
    if not ANTHROPIC_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 500
    
    data = request.get_json(force=True)
    user_text = (data.get("text") or "").strip()
    
    if not user_text:
        return jsonify({"error": "Empty message"}), 400
    
    # Get agent and respond
    sid = _sid()
    agent = _get_agent(sid)
    result = agent.respond(user_text, language=data.get("language", "en"))
    
    # Generate TTS if requested
    audio_url = None
    if ELEVENLABS_KEY and data.get("tts", True):
        tts_result = synthesize_elevenlabs(result["response"], ELEVENLABS_KEY, VOICE_ID)
        if tts_result["success"]:
            audio_id = str(uuid.uuid4())
            _audio_cache[audio_id] = tts_result["audio"]
            audio_url = f"/api/audio/{audio_id}"
    
    return jsonify({
        "transcript": user_text,
        "reply": result["response"],
        "intent": result.get("intent", ""),
        "escalated": result.get("should_escalate", False),
        "handoff_summary": result.get("handoff_summary"),
        "audio_url": audio_url,
    })


# ── SocketIO Events ────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    """Client connects."""
    join_room(request.sid)
    sid = _sid()
    socket_id = request.sid
    
    logger.info(f"[Connect] sid={sid[:8]} socket={socket_id[:8]}")
    
    # Emit connection info
    emit("connected", {
        "sid": sid,
        "deepgram_available": bool(DEEPGRAM_KEY),
        "elevenlabs_available": bool(ELEVENLABS_KEY),
        "simli_available": bool(SIMLI_API_KEY and SIMLI_FACE_ID),
    })
    
    # Auto-greet on page load
    socketio.start_background_task(_run_turn, sid, "__greet__", socket_id, "en")


@socketio.on("start_stream")
def on_start_stream():
    """Start live streaming (Deepgram STT)."""
    if not DEEPGRAM_KEY:
        emit("stream_error", {"error": "No DEEPGRAM_API_KEY configured"})
        return
    
    socket_id = request.sid
    sid = _sid()
    
    # Stop any existing stream
    if sid in _streams:
        _streams[sid].stop()
    
    # Callback for transcription results
    def on_transcript(text: str, is_final: bool, language: str = "en"):
        if is_final:
            # Final transcript → run turn in background
            socketio.start_background_task(_run_turn, sid, text, socket_id, language)
        else:
            # Interim results → show for UX feedback
            socketio.emit("partial_transcript", {"text": text}, room=socket_id)
    
    # Create and start stream
    stream = DeepgramStreamSession(DEEPGRAM_KEY, on_transcript)
    stream.start()
    _streams[sid] = stream
    
    emit("stream_ready", {"status": "listening"})
    logger.info(f"[Stream] Started for sid={sid[:8]}")


@socketio.on("audio_chunk")
def on_audio_chunk(data):
    """Receive audio chunk from browser (PCM audio)."""
    sid = _sid()
    if sid in _streams:
        # data is bytes (from audioworklet processor)
        chunk = data if isinstance(data, bytes) else bytes(data)
        _streams[sid].send_audio(chunk)


@socketio.on("resume_stream")
def on_resume_stream():
    """Resume streaming after reply finishes."""
    sid = _sid()
    
    # If stream still alive, don't restart
    if sid in _streams and _streams[sid].is_alive():
        return
    
    if not DEEPGRAM_KEY:
        return
    
    socket_id = request.sid
    
    # Restart stream
    def on_transcript(text: str, is_final: bool, language: str = "en"):
        if is_final:
            socketio.start_background_task(_run_turn, sid, text, socket_id, language)
        else:
            socketio.emit("partial_transcript", {"text": text}, room=socket_id)
    
    stream = DeepgramStreamSession(DEEPGRAM_KEY, on_transcript)
    stream.start()
    _streams[sid] = stream
    
    logger.info(f"[Stream] Resumed for sid={sid[:8]}")


@socketio.on("stop_stream")
def on_stop_stream():
    """Stop streaming."""
    sid = _sid()
    if sid in _streams:
        _streams[sid].stop()
        del _streams[sid]
        logger.info(f"[Stream] Stopped for sid={sid[:8]}")


@socketio.on("disconnect")
def on_disconnect():
    """Client disconnects."""
    sid = session.get("sid")
    if not sid:
        return
    
    # Clean up
    if sid in _streams:
        _streams[sid].stop()
        del _streams[sid]
    
    # Log call to n8n if escalated/resolved
    if sid in _call_meta:
        meta = _call_meta[sid]
        fire_n8n_webhook(
            call_id=meta["call_id"],
            intent="general",  # TODO: track actual intent
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
    
    logger.info(f"[Disconnect] sid={sid[:8]}")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    
    logger.info(f"Starting InsurVoice AI on port {port}")
    logger.info(f"ANTHROPIC: {'✅' if ANTHROPIC_KEY else '❌'}")
    logger.info(f"DEEPGRAM: {'✅' if DEEPGRAM_KEY else '❌'}")
    logger.info(f"ELEVENLABS: {'✅' if ELEVENLABS_KEY else '❌'}")
    logger.info(f"SIMLI: {'✅' if SIMLI_API_KEY else '❌'}")
    
    # Run with gevent
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False,
        log_output=True,
    )
