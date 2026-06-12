"""
stream.py
---------
Live speech-to-text using Deepgram SDK (handles Windows/Python 3.12 correctly).

Two modes:
  LIVE  — DeepgramStreamSession via official SDK WebSocket
  BATCH — transcribe_streaming_chunk via Deepgram REST (file uploads)
"""

import requests


def transcribe_streaming_chunk(audio_bytes: bytes, api_key: str) -> dict:
    """
    Single-shot transcription via Deepgram REST API.
    Used for file uploads and as a reliable fallback.
    """
    if not api_key:
        return {"success": False, "text": "", "error": "No Deepgram API key"}
    if not audio_bytes or len(audio_bytes) < 100:
        return {"success": False, "text": "", "error": "Audio too short"}
    try:
        resp = requests.post(
            "https://api.deepgram.com/v1/listen"
            "?model=nova-2&punctuate=true&language=en",
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "audio/webm",
            },
            data=audio_bytes,
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            text = (data.get("results", {})
                       .get("channels", [{}])[0]
                       .get("alternatives", [{}])[0]
                       .get("transcript", "")
                       .strip())
            if not text:
                return {"success": False, "text": "", "error": "Empty transcript"}
            return {"success": True, "text": text, "error": None}
        elif resp.status_code == 401:
            return {"success": False, "text": "", "error": "Invalid Deepgram API key"}
        else:
            return {"success": False, "text": "", "error": f"Deepgram error {resp.status_code}"}
    except Exception as e:
        return {"success": False, "text": "", "error": str(e)[:100]}


class DeepgramStreamSession:
    """
    Live streaming STT using the official Deepgram Python SDK.
    Works correctly on Windows + Python 3.12.
    """

    def __init__(self, api_key: str, on_transcript):
        self.api_key = api_key
        self.on_transcript = on_transcript
        self._connection = None
        self._thread = None
        self._running = False
        self._queue = None

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
        if self._connection and self._running:
            try:
                self._connection.send(chunk)
            except Exception:
                pass

    def _run(self):
        try:
            from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
        except ImportError:
            self.on_transcript("[Install deepgram-sdk: pip install deepgram-sdk]", True)
            return

        try:
            dg = DeepgramClient(self.api_key)
            conn = dg.listen.websocket.v("1")
            self._connection = conn

            def on_message(self_inner, result, **kwargs):
                try:
                    sentence = result.channel.alternatives[0].transcript
                    is_final = result.is_final
                    if sentence:
                        self.on_transcript(sentence, is_final)
                except Exception:
                    pass

            def on_error(self_inner, error, **kwargs):
                self.on_transcript(f"[stream error: {error}]", True)

            conn.on(LiveTranscriptionEvents.Transcript, on_message)
            conn.on(LiveTranscriptionEvents.Error, on_error)

            opts = LiveOptions(
                model="nova-2",
                language="en",
                punctuate=True,
                interim_results=True,
                endpointing=500,
                encoding="linear16",
                sample_rate=16000,
                channels=1,
            )

            if conn.start(opts):
                # Keep thread alive while running
                import time
                while self._running:
                    time.sleep(0.1)
                conn.finish()
            else:
                self.on_transcript("[Could not connect to Deepgram]", True)

        except Exception as e:
            self.on_transcript(f"[stream error: {str(e)[:80]}]", True)
