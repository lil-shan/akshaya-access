from backend import Backend


def test_backend_url_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://localhost:9999")
    assert str(Backend().http.base_url) == "http://localhost:9999"


def test_backend_url_defaults_to_localhost_8000(monkeypatch):
    monkeypatch.delenv("BACKEND_URL", raising=False)
    assert str(Backend().http.base_url) == "http://localhost:8000"


def test_calls_to_the_backend_never_go_through_a_proxy_from_the_environment(monkeypatch):
    monkeypatch.setenv("ALL_PROXY", "socks5h://localhost:1080")
    monkeypatch.setenv("HTTP_PROXY", "http://localhost:3128")
    assert Backend().http.trust_env is False
