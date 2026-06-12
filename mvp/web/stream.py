"""
stream.py — InsurVoice AI · Deepgram direct WebSocket STT
Language detection only on long non-ASCII text to avoid false positives.
"""

import requests
import threading
import json
import time


def detect_language(text: str) -> str:
    """
    Detect language only when text is long enough and contains non-ASCII chars.
    Short or pure-ASCII text defaults to English to avoid false positives.
    """
    if not text or len(text) < 20:
        return "en"
    # Pure ASCII = almost certainly English (no umlauts, accents etc.)
    if all(ord(c) < 128 for c in text):
        return "en"
    try:
        from langdetect import detect
        lang = detect(text)
        # Only trust languages we explicitly support
        if lang in {"de", "es", "fr", "it", "nl", "pt", "pl"}:
            return lang
        return "en"
    except Exception:
        return "en"


def transcribe_chunk(audio_bytes: bytes, api_key: str) -> dict:
    if not api_key:
        return {"success": False, "text": "", "language": "en", "error": "No DEEPGRAM_API_KEY"}
    if not audio_bytes or len(audio_bytes) < 100:
        return {"success": False, "text": "", "language": "en", "error": "Audio too short"}
    try:
        r = requests.post(
            "https://api.deepgram.com/v1/listen?model=nova-2-general&punctuate=true",
            headers={"Authorization": f"Token {api_key}", "Content-Type": "audio/webm"},
            data=audio_bytes, timeout=30,
        )
        if r.status_code == 200:
            text = (r.json().get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [{}])[0]
                    .get("transcript", "").strip())
            lang = detect_language(text) if text else "en"
            return {"success": bool(text), "text": text, "language": lang,
                    "error": None if text else "Empty transcript"}
        return {"success": False, "text": "", "language": "en",
                "error": f"Deepgram {r.status_code}"}
    except Exception as e:
        return {"success": False, "text": "", "language": "en", "error": str(e)[:80]}


transcribe_streaming_chunk = transcribe_chunk


class DeepgramStreamSession:
    # nova-2-general handles multiple languages including German, Spanish, French
    WS_URL = (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-2-general&encoding=linear16&sample_rate=16000"
        "&channels=1&punctuate=true&interim_results=true&endpointing=600"
    )

    def __init__(self, api_key: str, on_transcript):
        self.api_key = api_key
        self.on_transcript = on_transcript
        self._running = False
        self._thread = None
        self._audio_queue = []
        self._lock = threading.Lock()
        self._started = threading.Event()
        self._last_final = ""
        self._last_final_time = 0

    def start(self):
        self._running = True
        self._started.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._started.wait(timeout=3)

    def stop(self):
        self._running = False

    def is_alive(self):
        return self._running and self._thread and self._thread.is_alive()

    def send_audio(self, chunk: bytes):
        if self._running:
            with self._lock:
                self._audio_queue.append(chunk)

    def _pop_audio(self):
        with self._lock:
            chunks = self._audio_queue[:]
            self._audio_queue.clear()
        return chunks

    def _is_duplicate(self, text: str) -> bool:
        now = time.time()
        if text == self._last_final and (now - self._last_final_time) < 3.0:
            return True
        if (now - self._last_final_time) < 2.0:
            a, b = text.lower(), self._last_final.lower()
            if a in b or b in a:
                return True
        return False

    def _run(self):
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
                    self._started.set()

                    async def sender():
                        while self._running:
                            for chunk in self._pop_audio():
                                try:
                                    await ws.send(chunk)
                                except Exception:
                                    return
                            await asyncio.sleep(0.02)
                        try:
                            await ws.send(json.dumps({"type": "CloseStream"}))
                        except Exception:
                            pass

                    async def receiver():
                        async for msg in ws:
                            try:
                                data = json.loads(msg)
                                if data.get("type") == "Results":
                                    alts = data.get("channel", {}).get("alternatives", [{}])
                                    text = alts[0].get("transcript", "").strip()
                                    is_final = data.get("is_final", False)
                                    if text and len(text) >= 3:
                                        if is_final:
                                            if self._is_duplicate(text):
                                                continue
                                            self._last_final = text
                                            self._last_final_time = time.time()
                                            lang = detect_language(text)
                                            self.on_transcript(text, True, lang)
                                        else:
                                            self.on_transcript(text, False, "en")
                            except Exception:
                                continue

                    await asyncio.gather(sender(), receiver())

            except Exception as e:
                self._started.set()
                err = str(e).lower()
                if "401" in err or "403" in err:
                    self.on_transcript("Invalid Deepgram API key", True, "en")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_stream())
        finally:
            self._running = False
            loop.close()
