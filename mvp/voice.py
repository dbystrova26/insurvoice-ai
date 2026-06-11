"""
voice.py
--------
Voice processing for InsurVoice AI.

Speech-to-text:  OpenAI Whisper API (whisper-1)
Text-to-speech:  ElevenLabs API

Both have free/cheap tiers. Keys are read from environment or passed in.

Design note: this module is channel-agnostic. The same agent logic (agent.py)
works whether input arrives as text, microphone audio, or an uploaded file.
The voice layer is purely an input/output wrapper.
"""

import io
import os
import requests


# ── Speech-to-Text: OpenAI Whisper ───────────────────────────────────────────

def transcribe_whisper(audio_bytes: bytes, api_key: str, filename: str = "audio.wav") -> dict:
    """
    Transcribes audio to text using OpenAI's Whisper API.

    Args:
        audio_bytes: raw audio file bytes (wav, mp3, m4a, webm all accepted)
        api_key: OpenAI API key
        filename: hint for the file type (extension matters to the API)

    Returns:
        {"success": bool, "text": str, "error": str|None}
    """
    if not api_key:
        return {"success": False, "text": "", "error": "No OpenAI API key provided"}

    if not audio_bytes or len(audio_bytes) < 100:
        return {"success": False, "text": "", "error": "Audio is empty or too short"}

    try:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, io.BytesIO(audio_bytes), "audio/wav")},
            data={"model": "whisper-1", "language": "en"},
            timeout=60,
        )
        if resp.status_code == 200:
            text = resp.json().get("text", "").strip()
            if not text:
                return {"success": False, "text": "", "error": "Transcription was empty — try speaking more clearly"}
            return {"success": True, "text": text, "error": None}
        elif resp.status_code == 401:
            return {"success": False, "text": "", "error": "Invalid OpenAI API key"}
        else:
            return {"success": False, "text": "", "error": f"Whisper API error {resp.status_code}: {resp.text[:120]}"}
    except requests.Timeout:
        return {"success": False, "text": "", "error": "Whisper request timed out"}
    except Exception as e:
        return {"success": False, "text": "", "error": f"Transcription failed: {str(e)[:120]}"}


# ── Text-to-Speech: ElevenLabs ────────────────────────────────────────────────

# Default voice: "Rachel" — a clear, professional female voice in ElevenLabs' free tier.
# Voice IDs are public; users can swap for any voice in their account.
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel


def synthesize_elevenlabs(text: str, api_key: str,
                          voice_id: str = DEFAULT_VOICE_ID) -> dict:
    """
    Converts text to speech using ElevenLabs API.

    Args:
        text: text to speak (keep under ~2500 chars for free tier)
        api_key: ElevenLabs API key
        voice_id: ElevenLabs voice ID

    Returns:
        {"success": bool, "audio": bytes|None, "error": str|None}
    """
    if not api_key:
        return {"success": False, "audio": None, "error": "No ElevenLabs API key provided"}

    if not text or not text.strip():
        return {"success": False, "audio": None, "error": "No text to synthesize"}

    # Trim to protect the free-tier character budget
    text = text.strip()[:2500]

    try:
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": "eleven_turbo_v2_5",   # fast, low-latency, multilingual
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
            },
            timeout=45,
        )
        if resp.status_code == 200:
            return {"success": True, "audio": resp.content, "error": None}
        elif resp.status_code == 401:
            return {"success": False, "audio": None, "error": "Invalid ElevenLabs API key"}
        elif resp.status_code == 429:
            return {"success": False, "audio": None, "error": "ElevenLabs rate limit / quota exceeded"}
        else:
            return {"success": False, "audio": None, "error": f"ElevenLabs error {resp.status_code}: {resp.text[:120]}"}
    except requests.Timeout:
        return {"success": False, "audio": None, "error": "ElevenLabs request timed out"}
    except Exception as e:
        return {"success": False, "audio": None, "error": f"Synthesis failed: {str(e)[:120]}"}


def list_elevenlabs_voices(api_key: str) -> list:
    """Returns available voices for the account, or a sensible default list."""
    if not api_key:
        return [{"id": DEFAULT_VOICE_ID, "name": "Rachel (default)"}]
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key}, timeout=15,
        )
        if resp.status_code == 200:
            voices = resp.json().get("voices", [])
            return [{"id": v["voice_id"], "name": v["name"]} for v in voices[:10]]
    except Exception:
        pass
    return [{"id": DEFAULT_VOICE_ID, "name": "Rachel (default)"}]
