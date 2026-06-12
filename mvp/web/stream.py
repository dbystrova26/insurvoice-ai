"""
stream.py
---------
Live speech-to-text using Deepgram's streaming WebSocket API.

How it works:
  1. Browser captures raw microphone audio (PCM 16-bit, 16kHz)
  2. Sends it in small chunks over a WebSocket to our Flask server
  3. Flask forwards each chunk to Deepgram's live transcription WebSocket
  4. Deepgram sends back partial + final transcripts in real time
  5. When a final transcript arrives (is_final=True), we pass it to the agent
  6. Agent responds → ElevenLabs speaks the reply → audio sent back to browser

This gives a continuous, phone-call-like experience with no press-to-record button.

Deepgram free tier: 12,000 minutes/month — plenty for demos.
Get API key: https://console.deepgram.com
"""

import os
import json
import asyncio
import threading
import websockets
import requests


DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-2"           # best accuracy on free tier
    "&language=en"
    "&punctuate=true"         # adds punctuation to transcripts
    "&interim_results=true"   # sends partial transcripts as you speak
    "&endpointing=500"        # fires is_final after 500ms of silence
    "&encoding=linear16"      # raw PCM from browser
    "&sample_rate=16000"
    "&channels=1"
)


def transcribe_streaming_chunk(audio_chunk: bytes, api_key: str) -> dict:
    """
    Single-shot transcription via Deepgram REST API.
    Used as a reliable fallback when WebSocket streaming isn't available.
    """
    if not api_key:
        return {"success": False, "text": "", "error": "No Deepgram API key"}
    if not audio_chunk or len(audio_chunk) < 100:
        return {"success": False, "text": "", "error": "Audio too short"}
    try:
        resp = requests.post(
            "https://api.deepgram.com/v1/listen?model=nova-2&punctuate=true",
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "audio/webm",
            },
            data=audio_chunk,
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
    Manages a live Deepgram WebSocket session for one caller.

    Usage (called from the Flask-SocketIO handler):
        session = DeepgramStreamSession(api_key, on_transcript_callback)
        session.start()
        session.send_audio(chunk)   # call repeatedly as mic data arrives
        session.stop()
    """

    def __init__(self, api_key: str, on_transcript):
        self.api_key = api_key
        self.on_transcript = on_transcript  # callback(text: str, is_final: bool)
        self._ws = None
        self._loop = None
        self._thread = None
        self._running = False
        self._audio_queue = asyncio.Queue() if False else None  # created in thread

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._close(), self._loop)

    def send_audio(self, chunk: bytes):
        if self._loop and self._audio_queue:
            asyncio.run_coroutine_threadsafe(
                self._audio_queue.put(chunk), self._loop
            )

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._audio_queue = asyncio.Queue()
        try:
            self._loop.run_until_complete(self._stream())
        finally:
            self._loop.close()

    async def _stream(self):
        headers = {"Authorization": f"Token {self.api_key}"}
        try:
            async with websockets.connect(DEEPGRAM_URL, extra_headers=headers) as ws:
                self._ws = ws
                # Run sender and receiver concurrently
                await asyncio.gather(
                    self._send_audio(ws),
                    self._receive_transcripts(ws),
                )
        except Exception as e:
            self.on_transcript(f"[stream error: {str(e)[:60]}]", True)

    async def _send_audio(self, ws):
        while self._running:
            try:
                chunk = await asyncio.wait_for(self._audio_queue.get(), timeout=0.5)
                await ws.send(chunk)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
        # Signal end of stream to Deepgram
        try:
            await ws.send(json.dumps({"type": "CloseStream"}))
        except Exception:
            pass

    async def _receive_transcripts(self, ws):
        async for message in ws:
            try:
                data = json.loads(message)
                if data.get("type") == "Results":
                    alt = (data.get("channel", {})
                               .get("alternatives", [{}])[0])
                    text = alt.get("transcript", "").strip()
                    is_final = data.get("is_final", False)
                    if text:
                        self.on_transcript(text, is_final)
            except Exception:
                continue

    async def _close(self):
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
