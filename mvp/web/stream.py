"""
stream.py — InsurVoice AI · Deepgram live streaming STT
--------------------------------------------------------
Written for deepgram-sdk v7 (the version installed via pip install deepgram-sdk).

v7 API key differences from v3:
  - DeepgramClient(api_key=...) not DeepgramClient(api_key)
  - dg.listen.v1.connect() is a context manager, not dg.listen.websocket.v("1")
  - Audio sent via sock.send_media(bytes), not sock.send(bytes)
  - Events via sock.on(event_type, callback)
  - sock.start_listening() starts the receive loop

Deepgram free tier: 12,000 minutes/month.
Get key: https://console.deepgram.com
"""

import requests
import threading
import time


def transcribe_chunk(audio_bytes: bytes, api_key: str) -> dict:
    """
    REST transcription via Deepgram — used for file uploads.
    Returns {"success": bool, "text": str, "error": str|None}
    """
    if not api_key:
        return {"success": False, "text": "", "error": "No DEEPGRAM_API_KEY"}
    if not audio_bytes or len(audio_bytes) < 100:
        return {"success": False, "text": "", "error": "Audio too short"}
    try:
        r = requests.post(
            "https://api.deepgram.com/v1/listen?model=nova-2&punctuate=true",
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "audio/webm",
            },
            data=audio_bytes,
            timeout=30,
        )
        if r.status_code == 200:
            text = (r.json()
                    .get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [{}])[0]
                    .get("transcript", "")
                    .strip())
            if not text:
                return {"success": False, "text": "", "error": "Empty transcript"}
            return {"success": True, "text": text, "error": None}
        elif r.status_code == 401:
            return {"success": False, "text": "", "error": "Invalid Deepgram API key"}
        else:
            return {"success": False, "text": "", "error": f"Deepgram {r.status_code}"}
    except Exception as e:
        return {"success": False, "text": "", "error": str(e)[:80]}


# Alias — server.py imports this name
transcribe_streaming_chunk = transcribe_chunk


class DeepgramStreamSession:
    """
    Live streaming STT using deepgram-sdk v7.

    v7 uses a context-manager pattern:
        with dg.listen.v1.connect(...) as sock:
            sock.on(event, callback)
            sock.start_listening()
            sock.send_media(audio_bytes)
    """

    def __init__(self, api_key: str, on_transcript):
        self.api_key = api_key
        self.on_transcript = on_transcript
        self._sock = None
        self._thread = None
        self._running = False
        self._audio_queue = []
        self._queue_lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        try:
            if self._sock:
                self._sock.send_close_stream()
        except Exception:
            pass

    def send_audio(self, chunk: bytes):
        """Queue a PCM16 audio chunk to be sent to Deepgram."""
        if self._running:
            with self._queue_lock:
                self._audio_queue.append(chunk)

    def _drain_queue(self):
        """Send any queued audio chunks to Deepgram."""
        with self._queue_lock:
            chunks = self._audio_queue[:]
            self._audio_queue.clear()
        for chunk in chunks:
            try:
                if self._sock:
                    self._sock.send_media(chunk)
            except Exception:
                pass

    def _run(self):
        try:
            from deepgram import (
                DeepgramClient,
                ListenV1Encoding,
                ListenV1Model,
            )
            from deepgram.listen.v1 import ListenV1Results
        except ImportError as e:
            # Silent — don't show install instructions in chat
            return

        try:
            dg = DeepgramClient(api_key=self.api_key)

            def on_message(result):
                try:
                    text = (result.channel.alternatives[0].transcript or "").strip()
                    is_final = bool(result.is_final)
                    if text and len(text) >= 3:
                        self.on_transcript(text, is_final)
                except Exception:
                    pass

            # v7 context manager — runs until we exit the with block
            with dg.listen.v1.connect(
                model="nova-2",
                encoding="linear16",
                sample_rate=16000,
                channels=1,
                punctuate=True,
                interim_results=True,
                endpointing=600,
            ) as sock:
                self._sock = sock

                # Register transcript handler
                sock.on("Results", on_message)

                # Start the receive loop in a daemon thread
                listen_thread = threading.Thread(
                    target=sock.start_listening, daemon=True
                )
                listen_thread.start()

                # Main loop: drain audio queue until stopped
                while self._running:
                    self._drain_queue()
                    time.sleep(0.02)

                # Drain any remaining audio
                self._drain_queue()

        except Exception as e:
            err = str(e).lower()
            if "401" in err or "unauthorized" in err or "api_key" in err or "invalid" in err:
                self.on_transcript("Invalid Deepgram API key — check your .env file", True)
            # All other errors: silent (network hiccups etc)
