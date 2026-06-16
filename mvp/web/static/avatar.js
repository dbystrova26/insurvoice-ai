/**
 * avatar.js  –  browser-side SimliClient integration
 *
 * Key changes:
 * 1. SimliClient is initialized with server-provided session credentials
 *    (session_id + livekit_token), not a separate client-side API call.
 * 2. Audio is captured as webm/opus and sent to the server as base64 chunks.
 * 3. Retry loop is capped with exponential backoff (no more infinite retries).
 * 4. Socket.IO prefers WebSocket transport.
 */

import { SimliClient } from "simli-client";

// ── Socket.IO connection ────────────────────────────────────────────────────
const socket = io({
  transports: ["websocket", "polling"],   // Fix #2: try WebSocket first
  reconnectionAttempts: 5,
  reconnectionDelay: 2000,
});

// ── DOM refs ────────────────────────────────────────────────────────────────
const videoEl   = document.getElementById("simli-video");
const audioEl   = document.getElementById("simli-audio");
const statusEl  = document.getElementById("status");
const transcriptEl = document.getElementById("transcript");

// ── State ───────────────────────────────────────────────────────────────────
let simliClient   = null;
let mediaRecorder = null;
let retryCount    = 0;
const MAX_RETRIES = 3;

// ── SimliClient init ────────────────────────────────────────────────────────

/**
 * Initialize SimliClient using credentials supplied by the server.
 * The server already created the Simli session server-side and sent us:
 *   { session_id, token, livekit_url, livekit_token }
 */
async function initSimli({ session_id, token, livekit_url, livekit_token }) {
  setStatus("Connecting avatar…");

  simliClient = new SimliClient();

  // SimliClient config – use server-provided LiveKit credentials
  const config = {
    apiKey:        "",            // not needed when livekit_token is provided
    faceID:        "",            // not needed when session is pre-created
    handleSilence: true,

    // If Simli provides LiveKit credentials directly, use them:
    ...(livekit_url && livekit_token
      ? { livekitUrl: livekit_url, livekitToken: livekit_token }
      : { sessionId: session_id, sessionToken: token }),

    videoRef: videoEl,
    audioRef: audioEl,
  };

  simliClient.on("start", () => {
    retryCount = 0;
    setStatus("Avatar ready – speak now");
    startMicrophone();
  });

  simliClient.on("stop", () => {
    setStatus("Session ended");
    stopMicrophone();
  });

  simliClient.on("error", (err) => {
    console.error("SimliClient error:", err);
    handleSimliError();
  });

  simliClient.on("silent", () => {
    // avatar is idle – normal between utterances, not an error
  });

  try {
    await simliClient.start(config);
  } catch (err) {
    console.error("simliClient.start failed:", err);
    handleSimliError();
  }
}

function handleSimliError() {
  if (retryCount >= MAX_RETRIES) {
    setStatus("Avatar unavailable – please refresh the page");
    return;
  }
  retryCount++;
  const delay = retryCount * 3000;   // 3s, 6s, 9s backoff
  setStatus(`Retrying avatar (${retryCount}/${MAX_RETRIES})…`);
  setTimeout(() => socket.emit("request_session"), delay);
}

// ── Microphone capture ──────────────────────────────────────────────────────
// Browser MediaRecorder produces webm/opus – we send it as-is to the server.
// The server passes it directly to Deepgram (which accepts webm/opus natively).

async function startMicrophone() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // webm/opus is the browser default and what Deepgram expects
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    mediaRecorder = new MediaRecorder(stream, { mimeType });

    // Collect audio in 250 ms slices for low latency
    mediaRecorder.addEventListener("dataavailable", async (event) => {
      if (event.data.size === 0) return;
      const buffer = await event.data.arrayBuffer();
      const base64 = btoa(String.fromCharCode(...new Uint8Array(buffer)));
      socket.emit("user_audio", { audio: base64 });
    });

    mediaRecorder.start(250);   // 250 ms timeslice
    console.log("Microphone started, mimeType:", mimeType);
  } catch (err) {
    console.error("Microphone access denied:", err);
    setStatus("Microphone access denied. Please allow microphone and refresh.");
  }
}

function stopMicrophone() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    mediaRecorder = null;
  }
}

// ── Socket events ───────────────────────────────────────────────────────────

socket.on("connect", () => {
  console.log("Socket connected:", socket.id);
  setStatus("Connected – starting avatar…");
});

socket.on("disconnect", () => {
  setStatus("Disconnected");
  stopMicrophone();
});

socket.on("simli_session", (data) => {
  // Server created the Simli session and is handing us the credentials
  console.log("Received Simli session:", data.session_id);
  initSimli(data);
});

socket.on("transcript", ({ text, role }) => {
  if (!transcriptEl) return;
  const line = document.createElement("p");
  line.className = role === "user" ? "user-line" : "assistant-line";
  line.textContent = (role === "user" ? "You: " : "AI: ") + text;
  transcriptEl.appendChild(line);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
});

socket.on("error", ({ message }) => {
  console.error("Server error:", message);
  setStatus("Error: " + message);
});

// ── Helpers ─────────────────────────────────────────────────────────────────

function setStatus(msg) {
  console.log("[status]", msg);
  if (statusEl) statusEl.textContent = msg;
}
