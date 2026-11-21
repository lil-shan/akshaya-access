"""Request shapes for the Sarvam REST API (docs.sarvam.ai), checked against a mocked transport - no key, no network."""
import base64
import json

import httpx
import pytest

import sarvam


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=sarvam.API_URL)


def test_transcribe_posts_the_wav_to_saaras_and_returns_the_transcript(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    seen = {}

    def handler(request):
        seen.update(path=request.url.path, key=request.headers["api-subscription-key"], body=request.read())
        return httpx.Response(200, json={"request_id": "r1", "transcript": "അതെ", "language_code": "ml-IN"})

    assert sarvam.transcribe(b"RIFFfake-wav", client(handler)) == "അതെ"
    assert seen["path"] == "/speech-to-text" and seen["key"] == "test-key"
    assert b"RIFFfake-wav" in seen["body"] and b'name="file"' in seen["body"]
    for field, value in [("model", "saaras:v4"), ("language_code", "ml-IN"), ("mode", "codemix")]:
        assert f'name="{field}"\r\n\r\n{value}'.encode() in seen["body"]


def test_synthesize_posts_text_to_bulbul_and_decodes_the_wav(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    seen = {}

    def handler(request):
        seen.update(path=request.url.path, key=request.headers["api-subscription-key"], body=json.loads(request.content))
        return httpx.Response(200, json={"request_id": "r2", "audios": [base64.b64encode(b"RIFFspoken").decode()]})

    assert sarvam.synthesize("നമസ്കാരം", "ml-IN", client(handler)) == b"RIFFspoken"
    assert seen["path"] == "/text-to-speech" and seen["key"] == "test-key"
    assert seen["body"] == {"text": "നമസ്കാരം", "language_code": "ml-IN", "model": "bulbul:v3", "enable_preprocessing": True}


def test_missing_key_exits_with_a_clear_message(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exit_info:
        sarvam.api_key()
    assert "SARVAM_API_KEY" in str(exit_info.value)


def test_api_error_raises(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "bad-key")
    with pytest.raises(httpx.HTTPStatusError):
        sarvam.synthesize("നമസ്കാരം", "ml-IN", client(lambda request: httpx.Response(403, json={"error": {}})))
