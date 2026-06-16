"""
voice.py  –  ElevenLabs TTS producing PCM-16 audio for Simli

Fix #3: output_format changed from audio/mpeg → pcm_16000
Simli requires: 16 kHz, mono, 16-bit little-endian PCM.
"""

import os
import requests
import logging

log = logging.getLogger(__name__)

ELEVENLABS_KEY   = os.environ["ELEVENLABS_API_KEY"]
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")

# ElevenLabs PCM output formats understood by Simli
# pcm_16000  = 16 kHz mono 16-bit LE  ← use this
# pcm_22050  = 22 kHz mono 16-bit LE  (also acceptable)
PCM_FORMAT = "pcm_16000"


def synthesize_elevenlabs_pcm(text: str) -> bytes:
    """
    Call ElevenLabs TTS and return raw PCM bytes (no WAV header).
    Suitable for direct POST to Simli's /sendAudio endpoint.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}"

    headers = {
        "xi-api-key": ELEVENLABS_KEY,
        "Content-Type": "application/json",
        # Fix: request PCM, not MP3
        "Accept": "audio/pcm",
    }

    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "output_format": PCM_FORMAT,   # ← key fix
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)

    if resp.status_code != 200:
        log.error(
            "ElevenLabs error %s: %s",
            resp.status_code,
            resp.text[:300],
        )
        raise RuntimeError(f"ElevenLabs TTS failed: {resp.status_code}")

    pcm_bytes = resp.content
    log.info(
        "ElevenLabs returned %d PCM bytes (format=%s)",
        len(pcm_bytes),
        PCM_FORMAT,
    )
    return pcm_bytes


# ── Streaming variant (optional – faster first-packet latency) ──────────────

def synthesize_elevenlabs_pcm_stream(text: str):
    """
    Generator that yields PCM chunks as they arrive from ElevenLabs.
    Use this if you want to start sending audio to Simli before
    ElevenLabs has finished generating the full response.

    Usage:
        for chunk in synthesize_elevenlabs_pcm_stream(text):
            send_pcm_to_simli(session_id, token, chunk)
    """
    url = (
        f"https://api.elevenlabs.io/v1/text-to-speech"
        f"/{ELEVENLABS_VOICE}/stream"
    )

    headers = {
        "xi-api-key": ELEVENLABS_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/pcm",
    }

    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "output_format": PCM_FORMAT,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    with requests.post(
        url,
        json=payload,
        headers=headers,
        stream=True,
        timeout=60,
    ) as resp:
        if resp.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs stream failed: {resp.status_code} {resp.text[:200]}"
            )
        for chunk in resp.iter_content(chunk_size=4096):
            if chunk:
                yield chunk
