import io, json, threading, time
import pypdf, pytest
import pdf_filler, worker

class FakeDb:
    def __init__(self): self.prompts, self.events, self.job, self.case = {}, [], [], []
    def add_prompt(self, row): pid = str(len(self.prompts)); self.prompts[pid] = dict(row, answer=None); return pid
    def get_prompt(self, pid): return dict(self.prompts[pid])
    def set_prompt(self, pid, **kw): self.prompts[pid].update(kw)
    def set_job(self, jid, **kw): self.job.append(kw)
    def set_case(self, cid, s): self.case.append(s)
    def event(self, cid, type, message, data=None): self.events.append((type, message, json.dumps(data or {})))

JOB = {"id": "j1", "case_id": "c1"}

@pytest.mark.parametrize("sid", ["pmjjby_claim", "pmsby_claim"])
def test_pdf_filled_and_checklist(sid):
    r = pypdf.PdfReader(io.BytesIO(pdf_filler.fill(sid, {"insured_name": "Test Citizen", "claimant_ifsc": "SBIN0000001", "odd_key": "xyz"}, "123456", "j1")))
    text = "".join(p.extract_text() for p in r.pages)
    assert "Test Citizen" in text and "SBIN0000001" in text and "odd_key" in text and "DOCUMENT CHECKLIST" in text

def test_answer_used_once_then_nulled_and_not_logged():
    db = FakeDb()
    def answerer():
        time.sleep(.1); db.prompts["0"].update(answer="482913", status="answered")
    threading.Thread(target=answerer).start()
    kind, ans = worker.ask(db, JOB, [("otp", "x", None)], timeout=5, poll=.05)
    assert (kind, ans) == ("otp", "482913")
    assert db.prompts["0"]["answer"] is None and db.prompts["0"]["status"] == "used"
    assert "482913" not in json.dumps(db.events) and "482913" not in json.dumps(db.job)
    assert db.job[0]["status"] == "waiting_input" and db.case[0] == "waiting_citizen" and db.case[-1] == "running"

def test_two_prompts_first_answer_wins_other_cancelled():
    db = FakeDb()
    threading.Thread(target=lambda: (time.sleep(.1), db.prompts["1"].update(answer="12345", status="answered"))).start()
    kind, _ = worker.ask(db, JOB, [("captcha_audio", "a", "p.wav"), ("captcha_image", "i", "p.png")], timeout=5, poll=.05)
    assert kind == "captcha_image" and db.prompts["0"]["status"] == "cancelled"

def test_timeout():
    db = FakeDb()
    with pytest.raises(worker.InputTimeout, match="citizen_input_timeout"):
        worker.ask(db, JOB, [("otp", "x", None)], timeout=.2, poll=.05)
    assert db.prompts["0"]["status"] == "expired"
