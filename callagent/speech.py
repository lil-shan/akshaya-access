"""Sarvam Saaras (STT, codemix) + Bulbul (TTS) over REST, with a TTS cache and a hard call budget. Used by --audio only.
The key is read from the environment (db.load_env fills it from ../voice/.env); it is never printed."""
import base64
import hashlib
import io
import os
import re
import wave
from pathlib import Path

import httpx

API = "https://api.sarvam.ai"
CACHE = Path(__file__).resolve().parent / "tts_cache"
CALLS = 0                      # Sarvam calls made by this process (STT + TTS, cache hits excluded)
BUDGET = int(os.environ.get("SARVAM_CALL_BUDGET", "400"))


class BudgetExceeded(RuntimeError):
    pass


def _post(path, **kw):
    global CALLS
    if CALLS >= BUDGET:
        raise BudgetExceeded(f"Sarvam call budget {BUDGET} reached")
    key = os.environ.get("SARVAM_API_KEY", "")
    if not key.startswith("sk_"):
        raise RuntimeError("SARVAM_API_KEY is not set (audio mode needs it; use --text or --script otherwise)")
    CALLS += 1
    r = httpx.post(API + path, headers={"api-subscription-key": key}, timeout=40, **kw)
    r.raise_for_status()
    return r.json()


def transcribe(wav: bytes) -> str:
    data = {"model": "saaras:v4", "mode": "codemix", "language_code": "ml-IN"}
    return _post("/speech-to-text", files={"file": ("citizen.wav", wav, "audio/wav")}, data=data)["transcript"]


def _chunks(text: str, limit: int = 400) -> list[str]:
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.?!])\s+", text.strip()):
        if cur and len(cur) + len(sent) + 1 > limit:
            parts.append(cur)
            cur = ""
        cur = f"{cur} {sent}".strip()
    return parts + [cur] if cur else parts


def _join_wavs(wavs: list[bytes]) -> bytes:
    if len(wavs) == 1:
        return wavs[0]
    out, params = io.BytesIO(), None
    with wave.open(out, "wb") as w:
        for b in wavs:
            with wave.open(io.BytesIO(b)) as r:
                if params is None:
                    params = r.getparams()
                    w.setparams(params)
                w.writeframes(r.readframes(r.getnframes()))
    return out.getvalue()


def synthesize(text: str, speaker: str | None = None, lang: str = "ml-IN") -> bytes:
    """Agent text -> WAV. Cached on disk by hash of (text, lang, speaker)."""
    CACHE.mkdir(exist_ok=True)
    f = CACHE / (hashlib.sha256(f"{lang}|{speaker}|{text}".encode()).hexdigest()[:32] + ".wav")
    if f.exists():
        return f.read_bytes()
    wavs = []
    for part in _chunks(text):
        body = {"text": part, "target_language_code": lang, "model": "bulbul:v3"}
        if speaker:
            body["speaker"] = speaker
        wavs.append(base64.b64decode("".join(_post("/text-to-speech", json=body)["audios"])))
    wav = _join_wavs(wavs)
    f.write_bytes(wav)
    return wav


class AudioIO:
    """Microphone + speaker. Records until ~1.2 s of silence after speech (simple energy gate), max 20 s."""
    RATE = 16000

    def __init__(self):
        import sounddevice as sd  # noqa: needs PortAudio
        self.sd = sd
        self.transcript = []

    def say(self, text):
        print("AGENT:", text, flush=True)
        self.transcript.append(("agent", text))
        self.play(synthesize(text))

    def play(self, wav: bytes):
        import numpy as np
        with wave.open(io.BytesIO(wav)) as r:
            audio = np.frombuffer(r.readframes(r.getnframes()), dtype="<i2")
            self.sd.play(audio, r.getframerate())
            self.sd.wait()

    def hear(self, label=None):
        import numpy as np
        frames, quiet, spoke = [], 0, False
        with self.sd.InputStream(samplerate=self.RATE, channels=1, dtype="int16") as st:
            for _ in range(int(20 * self.RATE / 1600)):
                block, _ = st.read(1600)
                frames.append(block.copy())
                loud = np.abs(block).mean() > 500
                spoke, quiet = spoke or loud, 0 if loud else quiet + 1
                if spoke and quiet > 12:
                    break
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.RATE)
            w.writeframes(np.concatenate(frames).tobytes())
        text = transcribe(buf.getvalue()) if spoke else ""
        print("CITIZEN:", label or text, flush=True)
        self.transcript.append(("citizen", label or text))
        return text
