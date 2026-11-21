"""API Setu DigiLocker sandbox: OAuth 2.0 authorization-code + PKCE (S256). Used only when DIGILOCKER_* keys exist.
Endpoints per DigiLocker partner API (public/oauth2/1/authorize|token, oauth2/2/files/issued, oauth2/1/file/{uri}); override base with
DIGILOCKER_BASE_URL. Unverified against a live sandbox (no keys yet). Never log code/token/verifier."""
import base64, hashlib, secrets, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs
import requests
from payments import env

def base(): return env("DIGILOCKER_BASE_URL") or "https://api.digitallocker.gov.in"
def live(): return bool(env("DIGILOCKER_CLIENT_ID") and env("DIGILOCKER_CLIENT_SECRET") and env("DIGILOCKER_REDIRECT_URI"))

def pkce_pair():
    v = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    return v, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()

def auth_url(client_id, redirect_uri, state, challenge, root=None):
    return (root or base()) + "/public/oauth2/1/authorize?" + urlencode({"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri,
            "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})

def parse_callback(url_or_query, expected_state):
    """Accepts a full redirect URL, '?code=..&state=..' or 'code=..&state=..'. Returns code; raises on error / state mismatch."""
    q = parse_qs(urlparse(url_or_query).query if "?" in url_or_query or "://" in url_or_query else url_or_query)
    if q.get("error"): raise ValueError("digilocker_denied")
    if q.get("state", [None])[0] != expected_state: raise ValueError("state_mismatch")
    if not q.get("code"): raise ValueError("no_code")
    return q["code"][0]

def token_request(code, verifier):
    return {"code": code, "grant_type": "authorization_code", "client_id": env("DIGILOCKER_CLIENT_ID"), "client_secret": env("DIGILOCKER_CLIENT_SECRET"),
            "redirect_uri": env("DIGILOCKER_REDIRECT_URI"), "code_verifier": verifier}

class Callback:
    """Tiny local callback endpoint; redirect_uri must point at it (e.g. http://localhost:8787/callback)."""
    def __init__(self, redirect_uri, state):
        self.value = None; self.error = None; u = urlparse(redirect_uri); outer = self
        class H(BaseHTTPRequestHandler):
            def do_GET(s):
                try: outer.value = parse_callback(s.path, state)
                except ValueError as e: outer.error = str(e)
                s.send_response(200); s.send_header("Content-Type", "text/plain"); s.end_headers()
                s.wfile.write(b"Consent received. You can close this tab." if outer.value else b"Consent failed.")
            def log_message(s, *a): pass
        self.srv = HTTPServer((u.hostname or "127.0.0.1", u.port or 8787), H); threading.Thread(target=self.srv.serve_forever, daemon=True).start()
    def poll(self):
        if self.error: raise ValueError(self.error)
        return self.value
    def close(self): self.srv.shutdown(); self.srv.server_close()

def fetch_documents(code, verifier):
    """Exchange code, list issued docs, download each. Returns [(kind, filename, bytes)]."""
    t = requests.post(base() + "/public/oauth2/1/token", data=token_request(code, verifier), timeout=30)
    if t.status_code >= 400: raise RuntimeError(f"digilocker_token_failed:{t.status_code}")
    h = {"Authorization": "Bearer " + t.json()["access_token"]}; out = []
    items = requests.get(base() + "/public/oauth2/2/files/issued", headers=h, timeout=30).json().get("items", [])
    for it in items:
        r = requests.get(base() + "/public/oauth2/1/file/" + it["uri"], headers=h, timeout=60)
        if r.status_code == 200: out.append(((it.get("doctype") or "document").lower(), f"{(it.get('doctype') or 'doc')}-{len(out)+1}.pdf", r.content))
    return out
