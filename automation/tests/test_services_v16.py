"""v1.6 services: service.json integrity, PDF sheets, mock-portal kinds (HTTP level), voter_form8 replay, KWA via the Eko code path."""
import io, json, os, re, subprocess, sys, time, glob
from pathlib import Path
import pypdf, pytest, requests
HERE = Path(__file__).parent.parent; sys.path.insert(0, str(HERE))
import worker, pdf_filler, dry_run, payments
from test_dry_run import server, replay, STUB, page, H  # noqa: F401  (fixture + local replay server)

SVC = {Path(f).parent.name: json.load(open(f)) for f in glob.glob(str(HERE / "portals/*/service.json"))}
CATS = {"certificates", "insurance", "bills", "elections", "identity", "police", "agriculture", "employment"}
NEW = ["edistrict_nativity_certificate", "edistrict_residence_certificate", "edistrict_community_certificate", "edistrict_relationship_certificate", "ksmart_birth_certificate",
       "ration_card_add_member", "voter_form8", "kwa_water_bill", "pmfby_crop_loss", "pan_form49a_prep", "passport_prep", "epf_withdrawal_prep"]
OLD = ["pmjjby_claim", "pmsby_claim", "edistrict_income_certificate", "kseb_bill_payment", "voter_form6", "thuna_lost_property"]

def test_all_services_present(): assert set(SVC) >= set(NEW + OLD) and len(SVC) == 18

@pytest.mark.parametrize("sid", sorted(SVC))
def test_service_json_valid(sid):
    d = SVC[sid]; assert d["id"] == sid and d["category"] in CATS and d["tier"] in (1, 2, 3) and d["submission"] in ("pdf", "mock_portal", "portal_dry_run", "api")
    assert d["name"] and d["name_ml"] and d["notes"] and "http" in d["notes"] and isinstance(d["fee"], dict) and d["active"] is True
    keys = [f["key"] for f in d["fields"]]; assert len(keys) == len(set(keys))
    for f in d["fields"]:
        assert f["label"] and f["label_ml"] and f["ask_ml"] and f["type"] in ("text", "date", "number", "phone", "select", "yesno", "ifsc", "account_number", "email", "textarea"), f["key"]
        if f["type"] == "select": assert f["options"] and all(isinstance(o, str) and o for o in f["options"]), f["key"]
        if "aadhaar" in f["key"]: assert f["key"].endswith("last4")
        if f.get("pattern"): re.compile(f["pattern"])
    if sid in NEW: assert d["documents"] or sid == "kwa_water_bill"

@pytest.mark.parametrize("sid", ["pmfby_crop_loss", "pan_form49a_prep", "passport_prep", "epf_withdrawal_prep"])
def test_prep_sheet_pdf(sid):
    svc = SVC[sid]; data = {f["key"]: "Zed" + f["key"] for f in svc["fields"] if f["type"] in ("text", "number")}
    r = pypdf.PdfReader(io.BytesIO(pdf_filler.fill(sid, data, "123456", "j1"))); text = "".join(p.extract_text() for p in r.pages)
    assert "DOCUMENT CHECKLIST" in text and "citizen must submit on the official portal" in text and r.pages[0].mediabox.width < 600
    assert any(v in text for v in list(data.values())[:3])
    assert all(d["label"].split(" (")[0][:20] in text.replace("\n", " ") for d in svc["documents"][:1])
    if sid == "pmfby_crop_loss": assert "72 HOURS" in text

class FDb:
    def __init__(self): self.up, self.docs, self.ev = {}, [], []
    def upload(self, p, d, c): self.up[p] = d
    def add_document(self, *a): self.docs.append(a)
    def event(self, *a, **k): self.ev.append(a)
def test_run_pdf_dispatch_for_new_sheets():
    for sid in ("pmfby_crop_loss", "pan_form49a_prep", "passport_prep", "epf_withdrawal_prep"):
        db = FDb(); res = worker.run_pdf(db, {"id": "j"}, {"id": "c", "data": {}, "case_number": "1"}, {"id": sid})
        assert db.up["c/j/claim.pdf"][:4] == b"%PDF" and res["stopped_before_submit"] and res["output_pdf"] == "c/j/claim.pdf"

def test_mock_kinds_map_to_services():
    assert set(worker.MOCK_KINDS) == {s for s in SVC if SVC[s]["submission"] == "mock_portal"}

@pytest.fixture(scope="module")
def mock():
    port = 18799; p = subprocess.Popen([sys.executable, str(HERE / "mock_portals/edistrict/server.py"), str(port)]); base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try: requests.get(base + "/", timeout=1); break
        except Exception: time.sleep(.2)
    yield base; p.terminate()

@pytest.mark.parametrize("sid,kind", sorted(worker.MOCK_KINDS.items()))
def test_mock_portal_form_matches_service_json_and_never_submits(mock, sid, kind):
    D = HERE / "mock_portals/edistrict"; (D / "SUBMITTED").unlink(missing_ok=True); (D / "sms.log").unlink(missing_ok=True); s = requests.Session()
    s.get(mock + f"/?kind={kind}"); s.post(mock + "/send-otp", data={"mobile": "9000000000"}, allow_redirects=False)
    otp = (D / "sms.log").read_text().split()[-1]; assert s.post(mock + "/verify-otp", data={"otp": otp}, allow_redirects=False).status_code == 303
    s.get(mock + "/captcha"); cap = (D / "captcha_answer.txt").read_text().strip()
    assert (D / "tts_cache" / f"en-{cap}.wav").exists()  # spoken captcha comes from the Sarvam cache (no new TTS call)
    assert s.post(mock + "/verify-captcha", data={"captcha": cap}, allow_redirects=False).status_code == 303
    form = s.get(mock + "/form").text; names = set(re.findall(r"name=(\w+)", form)); want = {f["key"] for f in SVC[sid]["fields"] if f["key"] != "mobile"}
    assert names == want, (names ^ want)
    for f in SVC[sid]["fields"]:
        if f["type"] == "select": assert all(f"<option>{o}</option>" in form for o in f["options"])
    assert not (D / "SUBMITTED").exists()

def test_replay_voter_form8_stops_at_preview_and_never_submits(server, monkeypatch):
    monkeypatch.setitem(STUB, "/dashboard", page('<a id="form8-card" href="/form8">Shifting of residence / correction of entries (Form 8)</a><a id="logout" href="/bye">Logout</a>'))
    monkeypatch.setitem(STUB, "/form8", page('<div id="form8-section"><input name="epic_number"><input name="address_pincode"><button id="save-next" onclick="location=\'/preview\'">Save &amp; Next</button></div>'))
    res, db = replay(server, "voter_form8", "/login", {"epic_number": "ABC1234567", "address_pincode": "682001"})
    assert res["stopped_reason"] == "reached_preview" and "/SUBMIT" not in H.hits and "/bye" in H.hits
    assert "form8-filled" in db.up and "preview-preview" in db.up
    blob = json.dumps(db.events) + json.dumps(db.jobs)
    for secret in ("9876543210", "654321", "AB12CD", "ABC1234567"): assert secret not in blob
    assert all(p["answer"] is None for p in db.prompts.values())

def test_voter_form8_load_fields_from_service_json(): assert "epic_number" in [f["key"] for f in dry_run.load_fields("voter_form8")]

def test_kwa_bbps_fetch_uses_water_operator_and_service_pattern(monkeypatch):
    seen = {}
    class E:
        live = False; base = "x"
        def fetch_bill(self, c, m, sid=None): seen["sid"] = sid; return {"amount_inr": 120, "due_date": "2026-12-01", "provider": "EKO_MOCK_SERVER", "sandbox": True}
    monkeypatch.setattr(payments, "Eko", E); monkeypatch.setattr(payments, "start_eko_mock", lambda b: None)
    db = FDb(); db.merge_case_data = lambda *a: None
    res = worker.run_bbps_fetch(db, {"id": "j"}, {"id": "c", "service_id": "kwa_water_bill", "data": {"consumer_number": "1234567", "payer_mobile": "9000000000"}}, SVC["kwa_water_bill"])
    assert seen["sid"] == "kwa_water_bill" and res["amount_inr"] == 120
    with pytest.raises(worker.JobError, match="missing_fields: consumer_number"):
        worker.run_bbps_fetch(db, {"id": "j"}, {"id": "c", "service_id": "kwa_water_bill", "data": {"consumer_number": "12", "payer_mobile": "9000000000"}}, SVC["kwa_water_bill"])
    monkeypatch.setenv("EKO_KWA_OPERATOR_ID", "W1"); monkeypatch.setenv("EKO_KSEB_OPERATOR_ID", "K1")
    monkeypatch.undo(); assert payments.Eko.operator_id(payments.Eko(), "kwa_water_bill").startswith(("KWA", "W")) 
