import base64, hashlib, hmac, json, threading, time
from urllib.parse import urlparse, parse_qs
import pytest
import payments, worker, digilocker_real as dl
from test_automation import FakeDb

def test_eko_signature():
    h = payments.eko_headers("DEV", "ACCESS", ts_ms=1700000000000)
    exp = base64.b64encode(hmac.new(base64.b64encode(b"ACCESS"), b"1700000000000", hashlib.sha256).digest()).decode()
    assert h == {"developer_key": "DEV", "secret-key": exp, "secret-key-timestamp": "1700000000000"}

def test_parse_bill_and_pay():
    r = {"status": 0, "data": {"amount": "2870.0", "utilitycustomername": "Amit", "billDueDate": "20260728", "bbpstrxnrefid": ""}}
    b = payments.parse_bill(r, "ref1", "X"); assert b["amount_inr"] == 2870 and b["due_date"] == "2026-07-28" and b["bill_ref"] == "ref1" and b["sandbox"]
    with pytest.raises(RuntimeError): payments.parse_bill({"status": 1468, "data": {}}, "r", "X")
    assert payments.parse_pay({"status": 0, "data": {"tx_status": "0", "tid": "T1"}}, "r", "X")["reference"] == "T1"
    with pytest.raises(RuntimeError): payments.parse_pay({"status": 0, "data": {"tx_status": "1"}}, "r", "X")

def test_razorpay_simulated(monkeypatch, tmp_path):
    for k in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"): monkeypatch.setenv(k, "")
    monkeypatch.setenv("SIM_RAZORPAY_DIR", str(tmp_path)); rz = payments.Razorpay()
    l = rz.create_link(100, "r", "d"); assert not rz.live and l["short_url"].startswith("https://rzp.io/simulated/") and rz.status(l["id"]) == "created"
    payments.sim_mark_paid(l["id"]); assert rz.status(l["id"]) == "paid"

def test_razorpay_real_request_shape(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_x"); monkeypatch.setenv("RAZORPAY_KEY_SECRET", "s"); seen = {}
    class R:
        status_code = 200
        def json(self): return {"id": "plink_1", "short_url": "https://rzp.io/i/a", "status": "created"}
    monkeypatch.setattr(payments.requests, "post", lambda url, **kw: seen.update(post=(url, kw)) or R())
    monkeypatch.setattr(payments.requests, "get", lambda url, **kw: seen.update(get=(url, kw)) or R())
    rz = payments.Razorpay(); rz.create_link(2870, "case-1", "d"); rz.status("plink_1")
    url, kw = seen["post"]; assert url == "https://api.razorpay.com/v1/payment_links" and kw["auth"] == ("rzp_test_x", "s")
    assert kw["json"]["amount"] == 287000 and kw["json"]["currency"] == "INR" and kw["json"]["upi_link"] is True
    assert seen["get"][0] == "https://api.razorpay.com/v1/payment_links/plink_1" and seen["get"][1]["auth"] == ("rzp_test_x", "s")

def test_pkce_and_url():
    v, c = dl.pkce_pair()
    assert c == base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode() and 43 <= len(v) <= 128
    q = parse_qs(urlparse(dl.auth_url("CID", "http://localhost:8787/callback", "ST", c, root="https://x")).query)
    assert q["code_challenge_method"] == ["S256"] and q["code_challenge"] == [c] and q["state"] == ["ST"] and q["response_type"] == ["code"]

def test_callback_parsing():
    assert dl.parse_callback("http://localhost:8787/callback?code=ABC&state=S", "S") == "ABC"
    assert dl.parse_callback("code=ABC&state=S", "S") == "ABC"
    for bad in ("?code=A&state=other", "?error=access_denied&state=S", "?state=S"):
        with pytest.raises(ValueError): dl.parse_callback(bad, "S")

def test_callback_server_roundtrip():
    import requests
    cb = dl.Callback("http://127.0.0.1:18787/callback", "S1")
    try:
        requests.get("http://127.0.0.1:18787/callback?code=XYZ&state=S1"); assert cb.poll() == "XYZ"
    finally: cb.close()

def test_consent_amount():
    assert worker.consent_amount_ok(["I agree to pay Rs 2870 for KSEB"], 2870) and worker.consent_amount_ok(["₹2,870.00"], 2870)
    assert not worker.consent_amount_ok(["pay Rs 2800"], 2870) and not worker.consent_amount_ok(["no amount 2870"], 2870)

class PDb(FakeDb):
    def __init__(self, consents): super().__init__(); self.consents, self.pay = consents, {}
    def consent_texts(self, cid, kind): return self.consents
    def add_payment(self, row): self.pay["p"] = dict(row); return "p"
    def set_payment(self, pid, **kw): self.pay[pid].update(kw)

def case(bill): return {"id": "c1", "case_number": "123456", "data": {"consumer_number": "1" * 13, "payer_mobile": "9" * 10, **({"_bill": bill} if bill else {})}}
BILL = {"amount_inr": 2870, "customer_name": "A", "provider": "EKO_MOCK_SERVER"}

def test_guards():
    with pytest.raises(worker.JobError, match="missing_bill"): worker.run_payment_collect(PDb(["Rs 1"]), JOB, case(None))
    with pytest.raises(worker.JobError, match="missing_consent:payment"): worker.run_payment_collect(PDb([]), JOB, case(BILL))
    with pytest.raises(worker.JobError, match="amount_mismatch"): worker.run_payment_collect(PDb(["pay Rs 100"]), JOB, case(BILL))

JOB = {"id": "j1", "case_id": "c1"}

def test_payment_flow_simulated(monkeypatch, tmp_path):
    for k in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "EKO_DEVELOPER_KEY", "EKO_ACCESS_KEY"): monkeypatch.setenv(k, "")
    monkeypatch.setenv("SIM_RAZORPAY_DIR", str(tmp_path))
    monkeypatch.setattr(payments, "start_eko_mock", lambda url=None: None)
    monkeypatch.setattr(payments.Eko, "pay_bill", lambda self, *a: {"reference": "T9", "provider": "EKO_MOCK_SERVER", "status": "SUCCESS"})
    db = PDb(["I agree to pay Rs 2870"])
    def pay_later():
        time.sleep(.3)
        for _ in range(50):
            if db.pay: payments.sim_mark_paid(db.pay["p"]["reference"]); return
            time.sleep(.1)
    threading.Thread(target=pay_later).start()
    res = worker.run_payment_collect(db, JOB, case(BILL), poll=.05, timeout=10)
    assert db.pay["p"]["status"] == "confirmed" and res["eko"]["reference"] == "T9" and res["eko_reference"] == "T9" and res["short_url"].startswith("https://rzp.io/simulated/")
