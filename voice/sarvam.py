"""Sarvam REST adapter (https://docs.sarvam.ai): Saaras speech-to-text and Bulbul text-to-speech. Used only by --audio."""
import base64
import os
import sys

import httpx

API_URL = "https://api.sarvam.ai"
STT_MODEL = "saaras:v4"
STT_MODE = "codemix"  # Malayalam in Malayalam script, English words in Latin script, numbers as numerals
TTS_MODEL = "bulbul:v3"  # bulbul:v4-flash has no Malayalam persona voices


def api_key() -> str:
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        sys.exit("SARVAM_API_KEY is not set. Audio mode needs a Sarvam API key: export SARVAM_API_KEY=... "
                 "(or run the text simulator without --audio).")
    return key


def _post(path: str, client: httpx.Client | None, **body) -> dict:
    response = (client or httpx).post(API_URL + path, headers={"api-subscription-key": api_key()}, timeout=30, **body)
    response.raise_for_status()
    return response.json()


def transcribe(wav: bytes, client: httpx.Client | None = None) -> str:
    """Citizen audio (WAV, 16 kHz mono) -> text."""
    data = {"model": STT_MODEL, "mode": STT_MODE, "language_code": "ml-IN"}
    return _post("/speech-to-text", client, files={"file": ("citizen.wav", wav, "audio/wav")}, data=data)["transcript"]


def synthesize(text: str, language_code: str = "ml-IN", client: httpx.Client | None = None) -> bytes:
    """Agent text -> WAV bytes."""
    body = {"text": text, "language_code": language_code, "model": TTS_MODEL, "enable_preprocessing": True}
    return base64.b64decode("".join(_post("/text-to-speech", client, json=body)["audios"]))
