"""
stream.py — InsurVoice AI · Deepgram live streaming STT
--------------------------------------------------------
Uses deepgram-sdk v3+ (installed as deepgram-sdk>=3.0.0).
Sends PCM audio chunks from the browser mic to Deepgram in real time.
Returns final transcripts to the on_transcript callback.

Deepgram free tier: 12,000 minutes/month — more than enough for demos.
Get API key: https://console.deepgram.com
"""

import requests


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
            headers={"Authorization": f"Token {api_key}", "Content-Type": "audio/webm"},
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


# Keep old name as alias so server.py import still works
transcribe_streaming_chunk = transcribe_chunk


class DeepgramStreamSession:
    """
    Live streaming STT session using deepgram-sdk v3+.
    The browser sends raw PCM16 audio chunks via SocketIO.
    Deepgram returns partial + final transcripts in real time.
    Final transcripts trigger the on_transcript(text, is_final=True) callback.
    """

    def __init__(self, api_key: str, on_transcript):
        self.api_key = api_key
        self.on_transcript = on_transcript
        self._connection = None
        self._thread = None
        self._running = False

    def start(self):
        import threading
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        try:
            if self._connection:
                self._connection.finish()
        except Exception:
            pass

    def send_audio(self, chunk: bytes):
        """Forward a raw PCM16 audio chunk to Deepgram."""
        if self._connection and self._running:
            try:
                self._connection.send(chunk)
            except Exception:
                pass

    def _run(self):
        try:
            from deepgram import (
                DeepgramClient,
                LiveTranscriptionEvents,
                LiveOptions,
            )
        except ImportError:
            self.on_transcript("deepgram-sdk not installed — run: pip install deepgram-sdk", True)
            return

        try:
            dg = DeepgramClient(api_key=self.api_key)
            conn = dg.listen.websocket.v("1")
            self._connection = conn

            def on_message(self_inner, result, **kwargs):
                try:
                    alt = result.channel.alternatives[0]
                    text = alt.transcript.strip()
                    is_final = result.is_final
                    # Only fire callback if there is actual text
                    if text:
                        self.on_transcript(text, is_final)
                except Exception:
                    pass

            def on_error(self_inner, error, **kwargs):
                # Don't crash — just log silently
                pass

            def on_close(self_inner, close, **kwargs):
                self._running = False

            conn.on(LiveTranscriptionEvents.Transcript, on_message)
            conn.on(LiveTranscriptionEvents.Error, on_error)
            conn.on(LiveTranscriptionEvents.Close, on_close)

            opts = LiveOptions(
                model="nova-2",
                language="en",
                punctuate=True,
                interim_results=True,
                endpointing=600,       # fire is_final after 600ms silence
                encoding="linear16",   # raw PCM from browser AudioWorklet
                sample_rate=16000,
                channels=1,
            )

            if not conn.start(opts):
                self.on_transcript("Could not connect to Deepgram — check your API key", True)
                return

            import time
            while self._running:
                time.sleep(0.05)

            conn.finish()

        except Exception as e:
            # Surface real errors without the install message
            err = str(e)
            if "api_key" in err.lower() or "401" in err:
                self.on_transcript("Invalid Deepgram API key — check your .env", True)
            # All other errors: silent (don't show technical noise to caller)
