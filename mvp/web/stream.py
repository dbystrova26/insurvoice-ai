"""
stream.py - InsurVoice AI - Deepgram direct WebSocket STT
No SDK dependency - works on any Python/Windows version.
"""
import requests, threading, json, time

def transcribe_chunk(audio_bytes, api_key):
    if not api_key: return {"success":False,"text":"","error":"No DEEPGRAM_API_KEY"}
    if not audio_bytes or len(audio_bytes)<100: return {"success":False,"text":"","error":"Audio too short"}
    try:
        r = requests.post("https://api.deepgram.com/v1/listen?model=nova-2&punctuate=true",
            headers={"Authorization":f"Token {api_key}","Content-Type":"audio/webm"},
            data=audio_bytes,timeout=30)
        if r.status_code==200:
            text=(r.json().get("results",{}).get("channels",[{}])[0]
                  .get("alternatives",[{}])[0].get("transcript","").strip())
            return {"success":bool(text),"text":text,"error":None if text else "Empty"}
        return {"success":False,"text":"","error":f"Deepgram {r.status_code}"}
    except Exception as e:
        return {"success":False,"text":"","error":str(e)[:80]}

transcribe_streaming_chunk = transcribe_chunk

class DeepgramStreamSession:
    WS_URL = ("wss://api.deepgram.com/v1/listen"
              "?model=nova-2&encoding=linear16&sample_rate=16000"
              "&channels=1&punctuate=true&interim_results=true&endpointing=600")

    def __init__(self, api_key, on_transcript):
        self.api_key = api_key
        self.on_transcript = on_transcript
        self._running = False
        self._thread = None
        self._audio_queue = []
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def send_audio(self, chunk):
        if self._running:
            with self._lock:
                self._audio_queue.append(chunk)

    def _pop_audio(self):
        with self._lock:
            chunks = self._audio_queue[:]
            self._audio_queue.clear()
        return chunks

    def _run(self):
        import asyncio

        async def _stream():
            try:
                import websockets
                async with websockets.connect(
                    self.WS_URL,
                    additional_headers={"Authorization": f"Token {self.api_key}"},
                    ping_interval=20, ping_timeout=10,
                ) as ws:
                    async def sender():
                        while self._running:
                            for chunk in self._pop_audio():
                                try: await ws.send(chunk)
                                except: return
                            await asyncio.sleep(0.02)
                        try: await ws.send(json.dumps({"type":"CloseStream"}))
                        except: pass

                    async def receiver():
                        async for msg in ws:
                            try:
                                data = json.loads(msg)
                                if data.get("type")=="Results":
                                    text=(data.get("channel",{})
                                          .get("alternatives",[{}])[0]
                                          .get("transcript","").strip())
                                    is_final=data.get("is_final",False)
                                    if text and len(text)>=3:
                                        self.on_transcript(text, is_final)
                            except: continue

                    await asyncio.gather(sender(), receiver())
            except Exception as e:
                err=str(e).lower()
                if "401" in err or "403" in err:
                    self.on_transcript("Invalid Deepgram key - check .env", True)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try: loop.run_until_complete(_stream())
        finally: loop.close()
