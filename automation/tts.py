"""Sarvam Bulbul TTS for the mock portal's spoken captcha. One call per (digits, lang), cached on disk.
Key: SARVAM_API_KEY env var, else the last sk_ line of ../voice/.env. Never printed. Returns None on any failure."""
import base64, json, os, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent
CACHE = HERE / "mock_portals/edistrict/tts_cache"
URL = "https://api.sarvam.ai/text-to-speech"
LANGS = {"en": ("en-IN", lambda d: ", ".join(d)), "ml": ("ml-IN", lambda d: ", ".join(d))}
CALLS = 0  # TTS calls made by this process

def api_key():
    k = os.environ.get("SARVAM_API_KEY", "")
    if k.startswith("sk_"): return k
    f = HERE.parent / "voice/.env"
    if f.exists():
        vals = [l.split("=", 1)[1].strip().strip("\"'") for l in f.read_text().splitlines() if l.startswith("SARVAM_API_KEY=")]
        vals = [v for v in vals if v.startswith("sk_")]
        if vals: return vals[-1]
    return None

def speak_digits(digits, lang="en"):
    """WAV bytes of the digits spoken, or None (no key / call failed -> caller uses beeps)."""
    global CALLS
    CACHE.mkdir(exist_ok=True); f = CACHE / f"{lang}-{digits}.wav"
    if f.exists(): return f.read_bytes()
    key = api_key()
    if not key or not digits.isdigit(): return None
    code, fmt = LANGS[lang]
    body = json.dumps({"text": fmt(digits), "target_language_code": code, "model": "bulbul:v3"}).encode()
    try:
        CALLS += 1
        req = urllib.request.Request(URL, body, {"api-subscription-key": key, "Content-Type": "application/json"})
        wav = base64.b64decode(json.load(urllib.request.urlopen(req, timeout=20))["audios"][0])
        if wav[:4] != b"RIFF": return None
        f.write_bytes(wav); return wav
    except Exception: return None
