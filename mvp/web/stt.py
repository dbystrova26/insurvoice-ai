"""
stt.py  –  Deepgram speech-to-text

Fix #4: browser microphone sends webm/opus at 48 kHz, not linear16 at 16 kHz.
Configure Deepgram to accept the browser's native format instead of trying
to convert it client-side.
"""

import os
import requests
import logging

log = logging.getLogger(__name__)

DEEPGRAM_KEY = os.environ["DEEPGRAM_API_KEY"]

# Deepgram REST endpoint (pre-recorded, single-utterance)
DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


def transcribe_deepgram(audio_bytes: bytes) -> str:
    """
    Transcribe a single audio chunk from the browser.

    Browser MediaRecorder typically produces:
      • Container : webm
      • Codec     : opus
      • Sample rate: 48 000 Hz
      • Channels  : 1 (mono) or 2 (stereo)

    Deepgram accepts this natively – no client-side conversion needed.
    We just need to tell it the correct mimetype and NOT specify
    encoding/sample_rate (Deepgram auto-detects from the container).
    """
    headers = {
        "Authorization": f"Token {DEEPGRAM_KEY}",
        # Fix: tell Deepgram the actual format coming from the browser
        "Content-Type": "audio/webm;codecs=opus",
    }

    params = {
        "model":       "nova-2",
        "language":    "en-US",
        "smart_format": "true",
        "punctuate":   "true",
        # Do NOT set encoding= or sample_rate= here.
        # Deepgram detects both from the webm container header.
    }

    resp = requests.post(
        DEEPGRAM_URL,
        headers=headers,
        params=params,
        data=audio_bytes,
        timeout=20,
    )

    if resp.status_code != 200:
        log.error(
            "Deepgram error %s: %s",
            resp.status_code,
            resp.text[:300],
        )
        return ""

    try:
        result = resp.json()
        transcript = (
            result["results"]["channels"][0]
            ["alternatives"][0]
            ["transcript"]
        )
        confidence = (
            result["results"]["channels"][0]
            ["alternatives"][0]
            .get("confidence", 0)
        )
        log.info("Deepgram transcript (conf=%.2f): %s", confidence, transcript)
        return transcript.strip()
    except (KeyError, IndexError) as exc:
        log.error("Failed to parse Deepgram response: %s | %s", exc, resp.text[:200])
        return ""


# ── Streaming variant using Deepgram WebSocket ──────────────────────────────
# Use this if you want real-time interim transcripts while the user is speaking.
# Requires the deepgram-sdk package: pip install deepgram-sdk

def make_deepgram_streaming_options() -> dict:
    """
    Options dict for Deepgram's LiveTranscription (WebSocket) API.
    Pass to deepgram.transcription.live() from the deepgram-sdk.

    The browser sends webm/opus; Deepgram streaming accepts it with
    encoding=opus and sample_rate=48000.
    """
    return {
        "model":        "nova-2",
        "language":     "en-US",
        "encoding":     "opus",          # codec inside the webm container
        "sample_rate":  48000,           # browser default
        "channels":     1,
        "smart_format": True,
        "punctuate":    True,
        "interim_results": True,         # get words as they're spoken
        "endpointing":  300,             # ms of silence before utterance ends
    }
