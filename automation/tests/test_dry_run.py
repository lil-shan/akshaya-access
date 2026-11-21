"""Dry-run tests. NEVER touch a real portal: the replay serves saved snapshots locally and aborts every non-localhost request.
Pages not visible without logging in are minimal local stand-ins marked [assumed]."""
import sys, json, threading, time, http.server
from pathlib import Path
import pytest
HERE = Path(__file__).parent.parent; sys.path.insert(0, str(HERE))
import worker, dry_run
from dry_run import check_click, GuardError, DENY

# ---- guard unit tests
@pytest.mark.parametrize("text", ["Submit", "Final Submit", "Preview & Submit", "Confirm", "e-Sign", "eSign now", "Pay now", "Register", "I declare", "FINAL"])
def test_denylist_refuses_even_if_allowlisted(text):
    with pytest.raises(GuardError, match="denylist"): check_click("#go", text, {"#go"})   # allowlisted by mistake + instructed: still refused
def test_not_allowlisted_refused():
    with pytest.raises(GuardError, match="not_allowlisted"): check_click("#other", "Next", {"#go"})
def test_benign_allowed(): check_click("#go", "Save & Next", {"#go"}); check_click("#o", "Request OTP", {"#o"})
def test_denylist_selector_itself():
    with pytest.raises(GuardError): check_click("#final-submit", "OK", {"#final-submit"})

# ---- fake db
class Db:
    def __init__(self, consent=True): self.prompts, self.events, self.jobs, self.cases, self.up, self.docs, self.consent = {}, [], [], [], {}, [], consent
    def add_prompt(self, row): pid = str(len(self.prompts)); self.prompts[pid] = dict(row, answer=None); return pid
    def get_prompt(self, pid): return dict(self.prompts[pid])
    def set_prompt(self, pid, **kw): self.prompts[pid].update(kw)
    def set_job(self, jid, **kw): self.jobs.append(kw)
    def set_case(self, cid, s): self.cases.append(s)
    def event(self, cid, type, message, data=None): self.events.append((type, message, json.dumps(data or {})))
    def upload(self, path, data, ctype): self.up[path] = ctype
    def add_document(self, *a): self.docs.append(a)
    def has_consent(self, cid, kind): return self.consent and kind == "portal_dry_run"
ANS = {"field": "9876543210", "otp": "654321", "captcha_image": "AB12CD", "captcha_audio": "AB12CD"}
def auto_answer(db, stop):
    seen = set()
    while not stop.is_set():
        for pid, p in list(db.prompts.items()):
            if pid not in seen and p["status"] == "open":
                seen.add(pid)
                v = "Dummy@1234" if "assword" in p["prompt_text"] else ANS[p["kind"]]
                db.prompts[pid].update(answer=v, status="answered")
        time.sleep(.05)

def test_mobile_prompt_used_once_and_nulled():
    db = Db(); threading.Thread(target=lambda: (time.sleep(.1), db.prompts["0"].update(answer="9876543210", status="answered"))).start()
    kind, v = worker.ask(db, {"id": "j", "case_id": "c"}, [("field", "Mobile number registered for this login", None)], timeout=5, poll=.05)
    assert (kind, v) == ("field", "9876543210") and db.prompts["0"]["answer"] is None and db.prompts["0"]["status"] == "used"
    assert "9876543210" not in json.dumps(db.events) + json.dumps(db.jobs)

def test_requires_consent_and_dry_run_mode():
    svc = {"id": "voter_form6"}; case = {"id": "c", "data": {}}
    with pytest.raises(worker.JobError, match="missing_consent:portal_dry_run"): worker.run_portal_dry(Db(consent=False), {"id": "j", "case_id": "c", "mode": "dry_run"}, case, svc)
    with pytest.raises(worker.JobError, match="mode_not_dry_run"): worker.run_portal_dry(Db(), {"id": "j", "case_id": "c", "mode": "mock"}, case, svc)

# ---- local replay server
SNAP = HERE / "portals"
def page(body, title="x"): return f"<html><title>{title}</title><body>{body}</body></html>".encode()
STUB = {  # [assumed] stand-ins for pages not visible without logging in
 "/otp": page('<h1>OTP [assumed stand-in]</h1><input name="otp"><button id="verify-otp" onclick="location=\'/dashboard\'">Verify OTP</button>'),
 "/dashboard": page('<a id="form6-card" href="/form6">New registration for general electors (Form 6)</a><a id="logout" href="/bye">Logout</a><a href="/bye">Log out</a>'),
 "/form6": page('<div id="form6-section"><input name="first_name_en"><input name="surname_en"><input name="address_pincode"><select name="gender"><option>Male</option><option>Female</option></select>'
                '<button id="save-next" onclick="location=\'/preview\'">Save &amp; Next</button></div>'),
 "/preview": page('<div id="preview">Preview [assumed]</div><button id="final-submit" onclick="fetch(\'/SUBMIT\')">Submit</button><a href="/bye">Logout</a>'),
 "/t/login": page('<input name="userName"><input name="password"><input name="captcha"><img alt="captcha" src="/c.png"><button id="login-btn" onclick="location=\'/t/otp\'">Login</button>'),
 "/t/otp": page('<input name="otp"><button id="verify-otp" onclick="location=\'/t/dash\'">Verify</button>'),
 "/t/dash": page('<a id="lost-property-link" href="/t/new">Lost Property</a><a id="logout" href="/bye">Logout</a>'),
 "/t/new": page('<a id="new-lost-request" href="/t/form">New Lost Property Request</a><a id="logout" href="/bye">Logout</a>'),
 "/t/form": page('<div id="lost-form"><input name="lost_date"><textarea name="lost_description"></textarea><input name="item_name">'
                 '<button id="preview-btn" onclick="fetch(\'/SUBMIT\')">Preview &amp; Submit</button></div><a id="logout" href="/bye">Logout</a>'),
 "/bye": page("bye"),
}
class H(http.server.BaseHTTPRequestHandler):
    hits = []
    def log_message(self, *a): pass
    def do_GET(self):
        H.hits.append(self.path); p = self.path.split("?")[0]; ctype = "text/html"
        if p == "/login":   # REAL saved snapshot of voters.eci.gov.in/login, plus a [assumed] stand-in handler for the buttons
            body = (SNAP / "voter_form6/snapshots/login.html").read_bytes() + b"<script>document.querySelector('button.library-btn').disabled=false;document.querySelector('button.library-btn').addEventListener('click',e=>{e.preventDefault();location='/otp'});document.querySelector(\"img[alt='Read aloud captcha']\").addEventListener('click',()=>fetch('/generateVoiceCaptcha/x'))</script>"
        elif p == "/thuna":  # REAL saved snapshot of the Thuna home page; Login button opens the stand-in login page
            body = (SNAP / "thuna_lost_property/snapshots/home.html").read_bytes() + b"<script>document.querySelectorAll('button.signInbutton').forEach(b=>b.addEventListener('click',()=>{location='/t/login'}))</script>"
        elif p.startswith("/generateVoiceCaptcha"): body, ctype = b"RIFFfakeaudio", "audio/wav"
        elif p == "/c.png": body, ctype = b"\x89PNG", "image/png"
        elif p in STUB: body = STUB[p]
        else: self.send_error(404); return
        self.send_response(200); self.send_header("content-type", ctype); self.end_headers(); self.wfile.write(body)

@pytest.fixture(scope="module")
def server():
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"; s.shutdown()

def replay(server, service, path, data):
    from playwright.sync_api import sync_playwright
    H.hits.clear(); db = Db(); stop = threading.Event(); threading.Thread(target=auto_answer, args=(db, stop), daemon=True).start()
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True); ctx = b.new_context()
        external = []
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else (external.append(r.request.url), r.abort()))
        pg = ctx.new_page()
        try: res = dry_run.run_dry(pg, db, {"id": "j", "case_id": "c"}, {"id": "c", "data": data}, service, lambda p, n: db.up.setdefault(n, "shot"), worker.ask, base_url=server + path)
        finally: stop.set(); b.close()
    return res, db

def test_replay_voter_form6_stops_at_preview_and_never_submits(server):
    res, db = replay(server, "voter_form6", "/login", {"first_name_en": "Test", "address_pincode": "682001", "gender": "Female"})
    assert res["stopped_reason"] == "reached_preview"
    assert "/SUBMIT" not in H.hits and "/bye" in H.hits            # logged out, never submitted
    assert "/generateVoiceCaptcha/x" in H.hits and any(p.endswith("captcha.audio") for p in db.up)   # audio captcha path used
    assert "form6-section-filled" not in db.up and "form6-filled" in db.up and "preview-preview" in db.up
    blob = json.dumps(db.events) + json.dumps(db.jobs)
    for secret in ("9876543210", "654321", "AB12CD", "Dummy@1234"): assert secret not in blob
    assert all(p["answer"] is None for p in db.prompts.values())   # every relayed value nulled
    assert [p["kind"] for p in db.prompts.values()].count("field") == 1   # mobile asked exactly once

def test_replay_thuna_denylist_stops_at_preview_and_submit(server):
    res, db = replay(server, "thuna_lost_property", "/thuna", {"lost_date": "2026-11-01", "lost_description": "bag", "item_name": "Licence"})
    assert res["stopped_reason"] == "guard_refused_next"           # 'Preview & Submit' refused by the denylist
    assert "/SUBMIT" not in H.hits and "/bye" in H.hits
    kinds = [p["kind"] for p in db.prompts.values()]; assert kinds.count("field") == 2 and "captcha_audio" not in kinds  # mobile + password; image-only captcha
    assert "lost_form-filled" in db.up and "lost_form-stop" in db.up

def test_unknown_page_aborts_with_screenshot(server):
    with pytest.raises(dry_run.AbortRun, match="unknown_page"):
        from playwright.sync_api import sync_playwright
        db = Db()
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True); pg = b.new_page()
            try: dry_run.run_dry(pg, db, {"id": "j", "case_id": "c"}, {"id": "c", "data": {}}, "voter_form6", lambda p, n: db.up.setdefault(n, 1), worker.ask, base_url=server + "/bye")
            finally: b.close(); assert "unknown-page" in db.up

def test_aadhaar_page_stops(server):
    STUB["/aad"] = page('<input name="aadhaar_number" placeholder="Aadhaar">')
    from playwright.sync_api import sync_playwright
    db = Db()
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True); pg = b.new_page()
        r = dry_run.run_dry(pg, db, {"id": "j", "case_id": "c"}, {"id": "c", "data": {}}, "voter_form6", lambda p, n: db.up.setdefault(n, 1), worker.ask, base_url=server + "/aad"); b.close()
    assert r["stopped_reason"] == "aadhaar_citizen_enters_on_portal"

def test_page_structure_never_captures_values_or_paragraphs(server):
    STUB["/sens"] = page('<h1>Head</h1><p>SECRETPARAGRAPH</p><label for="m">Mobile</label><input id="m" name="mob" placeholder="Enter mobile" required>'
                         '<select name="g"><option>Male</option></select><textarea name="t"></textarea><button id="b">Next</button><a href="/x?tok=SECRETQ">Link</a>')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True); pg = b.new_page(); pg.goto(server + "/sens?q=SECRETQUERY")
        pg.fill("#m", "SECRETVALUE"); pg.fill("[name=t]", "SECRETTYPED"); d = dry_run.page_structure(pg); b.close()
    blob = json.dumps(d)
    for bad in ("SECRETVALUE", "SECRETTYPED", "SECRETPARAGRAPH", "SECRETQUERY", "SECRETQ"): assert bad not in blob
    assert d["path"] == "/sens" and d["headings"] == ["Head"] and any(c["id"] == "m" and c["label"] == "Mobile" and c["required"] for c in d["controls"])
    assert d["controls"][1]["options"] == ["Male"] and d["buttons"][0]["text"] == "Next"

@pytest.mark.parametrize("svc", ["voter_form6", "thuna_lost_property"])
def test_every_select_has_options_and_no_pattern(svc):
    for f in dry_run.load_fields(svc):
        if f["type"] == "select": assert f.get("options") and all(isinstance(o, str) and o for o in f["options"]) and not f.get("pattern"), f["key"]
