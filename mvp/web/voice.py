"""
voice.py – ElevenLabs TTS

Two functions:
  synthesize_elevenlabs_mp3()  – returns MP3 bytes
                                  Used by server.py → sent as audio_base64 to browser
                                  Browser plays audio + decodes MP3→PCM to send to Simli

  synthesize_elevenlabs_pcm()  – returns raw PCM16 bytes (kept for reference)
"""

import os
import requests
import logging

log = logging.getLogger(__name__)

ELEVENLABS_KEY   = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")


def synthesize_elevenlabs_mp3(text: str) -> bytes:
    """
    Return MP3 audio bytes from ElevenLabs.
    The browser receives this as base64, plays it with <audio>,
    and decodes it to PCM to feed Simli for lip-sync.
    """
    if not ELEVENLABS_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}"
    headers = {
        "xi-api-key":   ELEVENLABS_KEY,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }
    payload = {
        "text":     text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        log.error("ElevenLabs error %s: %s", resp.status_code, resp.text[:200])
        raise RuntimeError(f"ElevenLabs TTS failed: {resp.status_code}")

    log.info("ElevenLabs returned %d MP3 bytes", len(resp.content))
    return resp.content


def synthesize_elevenlabs_pcm(text: str) -> bytes:
    """
    Return raw PCM-16 bytes (16 kHz mono) from ElevenLabs.
    Use this only if you want to POST audio directly to Simli server-side.
    """
    if not ELEVENLABS_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}"
    headers = {
        "xi-api-key":   ELEVENLABS_KEY,
        "Content-Type": "application/json",
        "Accept":       "audio/pcm",
    }
    payload = {
        "text":          text,
        "model_id":      ELEVENLABS_MODEL,
        "output_format": "pcm_16000",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs TTS failed: {resp.status_code}")

    return resp.content
