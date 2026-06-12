"""
server.py — InsurVoice AI · Flask web server
----------------------------------------------
Serves the HTML voice interface and handles the voice pipeline server-side.

Why Flask (not Streamlit) for this version:
  - Full control over the HTML/CSS for a custom enterprise-AI look
  - API keys stay server-side (never exposed to the browser)
  - Cleaner deployment as a standard web service on Render

Pipeline:
  Browser records/uploads audio
    → POST /api/voice (multipart audio)
      → Whisper transcribes
      → Claude (InsurVoiceAgent) generates reply
      → ElevenLabs synthesizes reply audio
    → returns JSON { transcript, reply, intent, escalated, audio_base64 }

Run locally:  python server.py
Deploy:       gunicorn server:app   (see render.yaml)
"""

import os
import base64
from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv

from agents import Orchestrator
from voice import transcribe_whisper, synthesize_elevenlabs, DEFAULT_VOICE_ID

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "insurvoice-dev-secret-change-in-prod")

# Keys from environment (server-side only — never sent to browser)
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)

# Agent sessions kept per browser session id (simple in-memory store)
_agents: dict[str, Orchestrator] = {}


def _get_agent() -> Orchestrator:
    sid = session.get("sid")
    if not sid:
        import uuid
        sid = uuid.uuid4().hex
        session["sid"] = sid
    if sid not in _agents:
        _agents[sid] = Orchestrator(ANTHROPIC_KEY)
    return _agents[sid]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "anthropic": bool(ANTHROPIC_KEY),
        "whisper": bool(OPENAI_KEY),
        "elevenlabs": bool(ELEVENLABS_KEY),
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    agent = _get_agent()
    agent.reset()
    return jsonify({"status": "reset"})


@app.route("/api/text", methods=["POST"])
def handle_text():
    """Handle a typed message (text fallback mode)."""
    if not ANTHROPIC_KEY:
        return jsonify({"error": "Server missing ANTHROPIC_API_KEY"}), 500

    data = request.get_json(force=True)
    user_text = (data.get("text") or "").strip()
    if not user_text:
        return jsonify({"error": "Empty message"}), 400

    agent = _get_agent()
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
        "escalated": result.get("should_escalate", False),
        "handoff_summary": result.get("handoff_summary"),
        "route": result.get("route"),
        "agent_trace": result.get("agent_trace", []),
        "compliance": result.get("compliance", {}),
        "audio_base64": audio_b64,
    })


@app.route("/api/voice", methods=["POST"])
def handle_voice():
    """Handle audio input (mic recording or uploaded file)."""
    if not ANTHROPIC_KEY:
        return jsonify({"error": "Server missing ANTHROPIC_API_KEY"}), 500
    if not OPENAI_KEY:
        return jsonify({"error": "Server missing OPENAI_API_KEY (needed for transcription)"}), 500

    if "audio" not in request.files:
        return jsonify({"error": "No audio file in request"}), 400

    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()
    filename = audio_file.filename or "audio.webm"

    # 1. Transcribe
    stt = transcribe_whisper(audio_bytes, OPENAI_KEY, filename)
    if not stt["success"]:
        return jsonify({"error": f"Transcription failed: {stt['error']}"}), 502
    transcript = stt["text"]

    # 2. Reason
    agent = _get_agent()
    result = agent.respond(transcript)

    # 3. Synthesize reply
    tts_enabled = request.form.get("tts", "true").lower() == "true"
    audio_b64 = None
    if ELEVENLABS_KEY and tts_enabled:
        tts = synthesize_elevenlabs(result["response"], ELEVENLABS_KEY, VOICE_ID)
        if tts["success"]:
            audio_b64 = base64.b64encode(tts["audio"]).decode()

    return jsonify({
        "transcript": transcript,
        "reply": result["response"],
        "intent": result.get("intent", ""),
        "escalated": result.get("should_escalate", False),
        "handoff_summary": result.get("handoff_summary"),
        "route": result.get("route"),
        "agent_trace": result.get("agent_trace", []),
        "compliance": result.get("compliance", {}),
        "audio_base64": audio_b64,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
