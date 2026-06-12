"""
stream.py — InsurVoice AI · Deepgram STT
-----------------------------------------
Uses direct WebSocket (websockets library) instead of deepgram-sdk.
Avoids all SDK version compatibility issues.
Works on Python 3.10+ / Windows / any platform.
"""

import requests
import threading
import json
import time


def transcribe_chunk(audio_bytes: bytes, api_key: str) -> dict:
    """REST transcription for file uploads."""
    if not api_key:
        return {"success": False, "text": "", "error": "No DEEPGRAM_API_KEY"}
    if not audio_bytes or len(audio_bytes) < 100:
        return {"success": False, "text": "", "error": "Audio too short"}
    try:
        r = requests.post(
            "https://api.deepgram.com/v1/listen?model=nova-2&punctuate=true",
            headers={"Authorization": f"Token {api_key}", "Content-Type": "audio/webm"},
            data=audio_bytes, timeout=30,
        )
        if r.status_code == 200:
            text = (r.json().get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [{}])[0]
                    .get("transcript", "").strip())
            return {"success": bool(text), "text": text,
                    "error": None if text else "Empty transcript"}
        return {"success": False, "text": "",
                "error": f"Deepgram {r.status_code}: {r.text[:80]}"}
    except Exception as e:
        return {"success": False, "text": "", "error": str(e)[:80]}


transcribe_streaming_chunk = transcribe_chunk


class DeepgramStreamSession:
    """
    Live streaming STT via direct WebSocket to Deepgram.
    No SDK — just websockets library (already installed as deepgram-sdk dependency).
    Audio chunks sent from browser → Deepgram → transcripts → on_transcript callback.
    """

    WS_URL = (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-2&encoding=linear16&sample_rate=16000"
        "&channels=1&punctuate=true&interim_results=true&endpointing=600"
    )

    def __init__(self, api_key: str, on_transcript):
        self.api_key = api_key
        self.on_transcript = on_transcript
        self._running = False
        self._thread = None
        self._ws = None
        self._audio_queue = []
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def send_audio(self, chunk: bytes):
        if self._running:
            with self._lock:
                self._audio_queue.append(chunk)

    def _pop_audio(self):
        with self._lock:
            chunks = self._audio_queue[:]
            self._audio_queue.clear()
        return chunks

    def _run(self):
        """Run the WebSocket session using sync websockets."""
        import asyncio

        async def _stream():
            try:
                import websockets
                async with websockets.connect(
                    self.WS_URL,
                    additional_headers={"Authorization": f"Token {self.api_key}"},
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws

                    async def sender():
                        while self._running:
                            chunks = self._pop_audio()
                            for chunk in chunks:
                                try:
                                    await ws.send(chunk)
                                except Exception:
                                    return
                            await asyncio.sleep(0.02)
                        # Close stream
                        try:
                            await ws.send(json.dumps({"type": "CloseStream"}))
                        except Exception:
                            pass

                    async def receiver():
                        async for msg in ws:
                            try:
                                data = json.loads(msg)
                                if data.get("type") == "Results":
                                    alts = (data.get("channel", {})
                                            .get("alternatives", [{}]))
                                    text = alts[0].get("transcript", "").strip()
                                    is_final = data.get("is_final", False)
                                    # Detect language from Deepgram response
                                    detected_lang = (data.get("channel", {})
                                                     .get("detected_language", "en"))
                                    if text and len(text) >= 3:
                                        self.on_transcript(text, is_final, detected_lang)
                            except Exception:
                                continue

                    await asyncio.gather(sender(), receiver())

            except Exception as e:
                err = str(e).lower()
                if "401" in err or "403" in err or "invalid" in err:
                    self.on_transcript(
                        "Deepgram auth failed — check DEEPGRAM_API_KEY in .env", True
                    )
                # Other errors: silent

        # Run in a fresh event loop (avoids Windows event loop issues)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_stream())
        finally:
            loop.close()
