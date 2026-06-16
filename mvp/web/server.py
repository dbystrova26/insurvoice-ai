"""
server.py  –  Flask-SocketIO backend for InsurVoice AI avatar

Key fixes applied:
1. ElevenLabs PCM audio is piped to Simli via HTTP POST (not base64 to browser)
2. WebSocket transport enabled (Render supports it)
3. Simli session lifecycle managed server-side
4. Deepgram configured for webm/opus (browser default)
"""

import os
import base64
import threading
import requests
import logging

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

from voice import synthesize_elevenlabs_pcm   # see voice.py
from stt import transcribe_deepgram           # see stt.py
from llm import get_llm_response              # your existing LLM logic

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

# ── Fix #2: enable WebSocket – Render DOES support it ──────────────────────
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="gevent",
    transports=["websocket", "polling"],   # websocket first
    ping_timeout=60,
    ping_interval=25,
    logger=False,
    engineio_logger=False,
)

SIMLI_API_KEY   = os.environ["SIMLI_API_KEY"]
SIMLI_FACE_ID   = os.environ.get("SIMLI_FACE_ID", "tmp9i8bbq7")
ELEVENLABS_KEY  = os.environ["ELEVENLABS_API_KEY"]
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# Per-session Simli state  { sid: {"simli_session_id": str, "simli_token": str} }
sessions: dict[str, dict] = {}


# ── Simli session helpers ───────────────────────────────────────────────────

def create_simli_session(face_id: str) -> dict:
    """Create a new Simli session and return session_id + token."""
    resp = requests.post(
        "https://api.simli.ai/startAudioToVideoSession",
        json={
            "faceId": face_id,
            "isJPG": False,
            "apiKey": SIMLI_API_KEY,
            "syncAudio": True,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    log.info("Simli session created: %s", data.get("session_id"))
    return data   # keys: session_id, token (and maybe livekit_url)


def send_pcm_to_simli(session_id: str, token: str, pcm_bytes: bytes) -> None:
    """
    POST raw PCM-16 audio to Simli's audio-ingestion endpoint.
    Simli expects: 16 kHz, mono, 16-bit little-endian PCM.
    Docs: https://docs.simli.ai/api-reference/send-audio
    """
    try:
        resp = requests.post(
            "https://api.simli.ai/sendAudio",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "audio/pcm",
            },
            params={"sessionId": session_id},
            data=pcm_bytes,
            timeout=30,
        )
        if resp.status_code != 200:
            log.error("Simli sendAudio error %s: %s", resp.status_code, resp.text[:200])
        else:
            log.info("Sent %d PCM bytes to Simli session %s", len(pcm_bytes), session_id)
    except Exception as exc:
        log.error("send_pcm_to_simli failed: %s", exc)


# ── Socket events ───────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    sid = request.sid
    log.info("Client connected: %s", sid)
    try:
        simli = create_simli_session(SIMLI_FACE_ID)
        sessions[sid] = {
            "simli_session_id": simli["session_id"],
            "simli_token":      simli["token"],
        }
        # Send the LiveKit credentials to the browser so the
        # SimliClient JS can connect to the video/audio room.
        emit("simli_session", {
            "session_id":  simli["session_id"],
            "token":       simli["token"],
            # some Simli responses include these directly:
            "livekit_url": simli.get("livekit_url", ""),
            "livekit_token": simli.get("livekit_token", ""),
        })
    except Exception as exc:
        log.error("Failed to create Simli session for %s: %s", sid, exc)
        emit("error", {"message": "Avatar session could not be started."})


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    sessions.pop(sid, None)
    log.info("Client disconnected: %s", sid)


@socketio.on("user_audio")
def on_user_audio(data: dict):
    """
    Browser sends:  { "audio": "<base64 webm/opus chunk>" }
    We transcribe → LLM → TTS (PCM) → Simli.
    """
    sid = request.sid
    session = sessions.get(sid)
    if not session:
        emit("error", {"message": "No avatar session. Please reconnect."})
        return

    raw_audio = base64.b64decode(data["audio"])

    # 1. Transcribe (Deepgram, webm/opus – see stt.py)
    transcript = transcribe_deepgram(raw_audio)
    if not transcript:
        return

    log.info("[%s] User said: %s", sid, transcript)
    emit("transcript", {"text": transcript, "role": "user"})

    # 2. LLM response
    reply_text = get_llm_response(transcript)
    log.info("[%s] LLM reply: %s", sid, reply_text[:80])
    emit("transcript", {"text": reply_text, "role": "assistant"})

    # 3. TTS → PCM → Simli   (in a thread so we don't block the event loop)
    def _tts_and_send():
        try:
            pcm_bytes = synthesize_elevenlabs_pcm(reply_text)
            send_pcm_to_simli(
                session["simli_session_id"],
                session["simli_token"],
                pcm_bytes,
            )
        except Exception as exc:
            log.error("TTS/Simli pipeline error for %s: %s", sid, exc)
            socketio.emit("error", {"message": "Audio generation failed."}, to=sid)

    threading.Thread(target=_tts_and_send, daemon=True).start()


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/avatar")
def avatar():
    return render_template("avatar.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
