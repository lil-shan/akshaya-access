import parsing as P
from engine import Call
from tests.fakes import FakeDb, ScriptIO

PIN = "ഒരിക്കലും"


class Worker:
    """Simulated automation worker: opens prompts one group at a time, finishes when all answered."""
    def __init__(self, groups, result, status="succeeded"):
        self.groups, self.result, self.status, self.cur, self.seen = list(groups), result, status, None, {}

    def __call__(self, db, job, n):
        if job["status"] in ("succeeded", "failed"):
            return
        job["status"] = "running"
        if self.cur and not any(db.prompts[i]["status"] == "answered" for i in self.cur):
            return
        if self.cur:
            self.seen.update({db.prompts[i]["kind"]: db.prompts[i]["answer"] for i in self.cur if db.prompts[i]["answer"]})
            for i in self.cur:
                db.prompts[i]["answer"] = None; db.prompts[i]["status"] = "used" if db.prompts[i]["status"] == "answered" else "cancelled"
            self.cur = None
        if self.groups:
            self.cur = [db.add_prompt(job["id"], k, t, m)["id"] for k, t, m in self.groups.pop(0)]
            job["status"] = "waiting_input"
            return
        job.update(status=self.status, result=self.result, error=None if self.status == "succeeded" else "boom")


def call(db, lines, **kw):
    io = ScriptIO(lines)
    c = Call(io, db, poll=0.001, job_wait=1, **kw)
    c.run()
    return io, c


PDF_LINES = ["1", "1", "E2E Test Person", "അതെ", "123456789012", "അതെ", "SBIN 0001234", "അതെ", "12/03/1980", "അതെ", "ഇല്ല", "അതെ"]
PDF_RES = {"output_pdf": "x.pdf", "stopped_before_submit": True, "summary": "ok"}


def test_pdf_call_end_to_end():
    db = FakeDb("pdf", Worker([], PDF_RES))
    io, c = call(db, PDF_LINES, extra_data={"_e2e": True})
    case = next(iter(db.cases.values()))
    assert case["channel"] == "phone" and case["data"]["acct"] == "123456789012" and case["data"]["ifsc"] == "SBIN0001234"
    assert case["data"]["claimant_name"] == "E2E Test Person" and case["data"]["dob"] == "1980-03-12" and case["data"]["_e2e"] is True
    assert "AI" in io.said[0] and "UPI" in io.said[0]                      # says it is an AI, never asks the PIN
    assert any(P.digits_ml("123456789012") in s for s in io.said)           # digit-by-digit read back
    assert db.order == ["consent:automation_run", "job:fill_pdf"]            # consent before job
    assert db.consents[0]["channel"] == "phone"
    assert "PDF" in io.said[-1] and "സമർപ്പിച്ചിട്ടില്ല" in io.said[-1]
    assert db.events and all(e["actor"] == "voice" for e in db.events)


def test_validation_reasks_and_wrong_confirmation():
    lines = ["1", "1", "E2E Name", "അതെ", "12345", "9876543210123", "അല്ല", "123456789012", "അതെ", "SBIN 0001234", "അതെ", "12/03/1980", "അതെ", "ഇല്ല", "അതെ"]
    db = FakeDb("pdf", Worker([], PDF_RES))
    call(db, lines)
    assert next(iter(db.cases.values()))["data"]["acct"] == "123456789012"   # short number rejected, "no" re-asks


def test_consent_requires_strict_yes_and_blocks_job():
    db = FakeDb("pdf", Worker([], PDF_RES))
    io, _ = call(db, PDF_LINES[:-1] + ["yes but change the date", "yes but no", "maybe"])
    assert db.jobs == {} and db.consents == [] and "ഡ്രാഫ്റ്റ്" in io.said[-1]


def test_person_request_is_handoff_event_no_promise():
    db = FakeDb("pdf")
    io, _ = call(db, ["1", "1", "E2E Name", "അതെ", "123456789012", "ആളെ വേണം"])
    assert any(e["type"] == "handoff" for e in db.events) and db.jobs == {}
    assert "ഉറപ്പ്" in io.said[-1]


def test_unsupported_service_handoff():
    db = FakeDb("pdf")
    io, _ = call(db, ["pension", "pension", "pension"])
    assert db.cases == {} and "അക്ഷയ കേന്ദ്ര" in io.said[-1]


def test_known_phone_skips_name():
    db = FakeDb("pdf", Worker([], PDF_RES), citizens=[{"id": "c1", "full_name": "E2E Known", "phone_masked": "******4321"}])
    call(db, ["1", "1", "അതെ", "123456789012", "അതെ", "SBIN 0001234", "അതെ", "12/03/1980", "അതെ", "ഇല്ല", "അതെ"], phone="9000004321")
    case = next(iter(db.cases.values()))
    assert case["citizen_id"] == "c1" and case["data"]["claimant_name"] == "E2E Known"


def portal_db(groups, **kw):
    w = Worker(groups, {"stopped_before_submit": True, "screenshots": [], "summary": "s"}, **kw)
    return FakeDb("portal", w), w


PORTAL = ["1", "1", "E2E P", "അതെ", "9876543210", "അതെ", "അതെ"]


def test_otp_and_captcha_relayed_never_logged():
    db, w = portal_db([[("otp", "otp?", None)], [("captcha_audio", "c", "p/c.wav"), ("captcha_image", "c", "p/c.png")]])
    io, _ = call(db, PORTAL + ["OTP 4 8 2 9 1 3", "five one two three four"])
    assert w.seen == {"otp": "482913", "captcha_audio": "51234"}              # relayed once, to the prompt only
    assert io.played == 1 and "[OTP given]" in io.heard_labels and "[captcha answer given]" in io.heard_labels
    assert "482913" not in db.blob() and "51234" not in db.blob()
    assert "482913" not in " ".join(io.said)
    assert "അവസാന പേജ്" in io.said[-1]
    assert not any(p["status"] == "answered" and p["kind"] == "captcha_image" for p in db.prompts.values())


def test_password_and_field_prompts_redacted():
    db, w = portal_db([[("field", "Mobile number registered for this login", None)], [("password", "pw", None)]])
    io, _ = call(db, PORTAL + ["9 1 2 3 4 5 6 7 8 9", "hunter2secret"])
    assert w.seen == {"field": "9123456789", "password": "hunter2secret"}
    assert "hunter2secret" not in db.blob() + " ".join(io.said) and "9123456789" not in db.blob()
    assert "[password given]" in io.heard_labels and "[field value given]" in io.heard_labels


def test_confirm_prompt_yes_no():
    db, w = portal_db([[("confirm", "Continue?", None)]])
    call(db, PORTAL + ["അതെ"])
    assert w.seen == {"confirm": "yes"}


def test_captcha_image_only_hands_off_to_whatsapp():
    db, w = portal_db([[("captcha_image", "img", "p.png")]])
    io, _ = call(db, PORTAL)
    assert "വാട്സ്ആപ്പ്" in io.said[-1] and all(p["answer"] is None for p in db.prompts.values())
    assert any(e["type"] == "captcha_image_unsupported" for e in db.events)


def test_failed_job_reported_without_promises():
    db, _ = portal_db([], status="failed")
    io, _ = call(db, PORTAL)
    assert "ഒന്നും സമർപ്പിച്ചിട്ടില്ല" in io.said[-1] and any("failed" in e["message"] for e in db.events)


API = ["1", "1", "E2E K", "അതെ", "1234567890123", "അതെ", "9876543210", "അതെ", "അതെ"]


def api_db():
    def worker(db, job, n):
        if job["status"] in ("succeeded", "failed"):
            return
        job["status"] = "succeeded"
        job["result"] = ({"customer_name": "X", "amount_inr": 2870, "due_date": "2026-12-01"} if job["kind"] == "bbps_fetch"
                         else {"payment_status": "confirmed", "upi_uri": None})
    return FakeDb("api", worker)


def test_payment_amount_read_back_and_consent_before_collect():
    db = api_db()
    io, _ = call(db, API + ["അതെ"])
    assert db.order == ["consent:automation_run", "job:bbps_fetch", "consent:payment", "job:payment_collect"]
    assert any(P.digits_ml("2870") in s and "2870" in s for s in io.said) and "പിൻ" in " ".join(io.said)
    pay = next(c for c in db.consents if c["kind"] == "payment")
    assert "₹2870" in pay["text"] and next(iter(db.cases.values()))["data"]["confirm_amount"] == "yes"
    assert "പേയ്മെന്റ് സ്ഥിരീകരിച്ചു" in io.said[-1]


def test_payment_declined_creates_no_collect_job():
    db = api_db()
    call(db, API + ["അല്ല"])
    assert "job:payment_collect" not in db.order and not any(c["kind"] == "payment" for c in db.consents)


def test_consumer_number_pattern_enforced():
    db = api_db()
    call(db, ["1", "1", "E2E K", "അതെ", "12345", "123", "1", "2"])
    assert "consumer_number" not in next(iter(db.cases.values()))["data"]
