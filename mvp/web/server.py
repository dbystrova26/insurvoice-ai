"""
server.py  –  Flask-SocketIO backend for InsurVoice AI avatar

Fixes applied:
1. ElevenLabs PCM audio piped to Simli (not base64 to browser)
2. WebSocket transport enabled (Render supports it)
3. Simli session lifecycle managed server-side
4. Deepgram configured for webm/opus (browser default)
5. Uses InsurVoiceAgent from agent.py (no llm.py needed)
"""

import os
import base64
import threading
import requests
import logging

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

from voice import synthesize_elevenlabs_pcm
from stt import transcribe_deepgram
from agent import InsurVoiceAgent

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET", "dev-secret")

# ── WebSocket enabled – Render supports it ──────────────────────────────────
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="gevent",
    transports=["websocket", "polling"],
    ping_timeout=60,
    ping_interval=25,
    logger=False,
    engineio_logger=False,
)

SIMLI_API_KEY     = os.environ["SIMLI_API_KEY"]
SIMLI_FACE_ID     = os.environ.get("SIMLI_FACE_ID", "tmp9i8bbq7")
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# Per-socket state
sessions: dict[str, dict] = {}
agents:   dict[str, InsurVoiceAgent] = {}


# ── Simli helpers ───────────────────────────────────────────────────────────

def create_simli_session(face_id: str) -> dict:
    """Create a Simli session server-side and return its credentials."""
    resp = requests.post(
        "https://api.simli.ai/startAudioToVideoSession",
        json={
            "faceId":    face_id,
            "isJPG":     False,
            "apiKey":    SIMLI_API_KEY,
            "syncAudio": True,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    log.info("Simli session created: %s", data.get("session_id"))
    return data


def send_pcm_to_simli(session_id: str, token: str, pcm_bytes: bytes) -> None:
    """POST raw PCM-16 audio to Simli. Expects 16kHz mono 16-bit LE."""
    try:
        resp = requests.post(
            "https://api.simli.ai/sendAudio",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "audio/pcm",
            },
            params={"sessionId": session_id},
            data=pcm_bytes,
            timeout=30,
        )
        if resp.status_code != 200:
            log.error("Simli sendAudio %s: %s", resp.status_code, resp.text[:200])
        else:
            log.info("Sent %d PCM bytes to Simli %s", len(pcm_bytes), session_id)
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
        agents[sid] = InsurVoiceAgent(api_key=ANTHROPIC_API_KEY)

        emit("simli_session", {
            "session_id":    simli["session_id"],
            "token":         simli["token"],
            "livekit_url":   simli.get("livekit_url", ""),
            "livekit_token": simli.get("livekit_token", ""),
        })
    except Exception as exc:
        log.error("Connect setup failed for %s: %s", sid, exc)
        emit("error", {"message": "Avatar session could not be started."})


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    sessions.pop(sid, None)
    agents.pop(sid, None)
    log.info("Client disconnected: %s", sid)


@socketio.on("user_audio")
def on_user_audio(data: dict):
    """
    Browser sends: { "audio": "<base64 webm/opus>" }
    Pipeline: Deepgram STT -> InsurVoiceAgent -> ElevenLabs PCM -> Simli
    """
    sid = request.sid
    session = sessions.get(sid)
    agent   = agents.get(sid)

    if not session or not agent:
        emit("error", {"message": "No session. Please reconnect."})
        return

    raw_audio = base64.b64decode(data["audio"])

    # 1. Transcribe
    transcript = transcribe_deepgram(raw_audio)
    if not transcript:
        return

    log.info("[%s] User: %s", sid, transcript)
    emit("transcript", {"text": transcript, "role": "user"})

    # 2. Agent response
    result     = agent.respond(transcript)
    reply_text = result["response"]
    log.info("[%s] Agent: %s", sid, reply_text[:80])
    emit("transcript", {"text": reply_text, "role": "assistant"})

    # Notify frontend if escalating to human
    if result.get("should_escalate"):
        emit("escalate", {
            "reason":  result.get("escalation_reason", ""),
            "summary": result.get("handoff_summary", ""),
        })

    # 3. TTS -> PCM -> Simli (background thread)
    def _tts_and_send():
        try:
            pcm_bytes = synthesize_elevenlabs_pcm(reply_text)
            send_pcm_to_simli(
                session["simli_session_id"],
                session["simli_token"],
                pcm_bytes,
            )
        except Exception as exc:
            log.error("TTS/Simli error for %s: %s", sid, exc)
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
