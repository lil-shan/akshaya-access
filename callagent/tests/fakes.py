import itertools
import uuid

from engine import Hangup


class ScriptIO:
    def __init__(self, lines):
        self.lines, self.said, self.heard_labels, self.played = list(lines), [], [], 0

    def say(self, t): self.said.append(t)
    def play(self, wav): self.played += 1

    def hear(self, label=None):
        if not self.lines:
            raise Hangup
        self.heard_labels.append(label)
        return self.lines.pop(0)


SERVICES = {
    "pdf": dict(id="pmjjby_claim", name="PMJJBY claim", name_ml="പിഎംജെജെബിവൈ ക്ലെയിം", category="insurance", submission="pdf", fields=[
        {"key": "claimant_name", "type": "text", "required": True, "source": "citizen.full_name", "ask_ml": "പേര്?"},
        {"key": "acct", "type": "account_number", "required": True, "ask_ml": "അക്കൗണ്ട് നമ്പർ?"},
        {"key": "ifsc", "type": "ifsc", "required": True, "ask_ml": "IFSC?"},
        {"key": "dob", "type": "date", "required": True, "ask_ml": "ജനനത്തീയതി?"},
        {"key": "policy", "type": "text", "required": False, "ask_ml": "പോളിസി?"}]),
    "portal": dict(id="edistrict_income_certificate", name="Income certificate", name_ml="വരുമാന സർട്ടിഫിക്കറ്റ്", category="certificates",
                   submission="mock_portal", fields=[{"key": "mobile", "type": "phone", "required": True, "ask_ml": "മൊബൈൽ?"}]),
    "api": dict(id="kseb_bill_payment", name="KSEB bill payment", name_ml="കെഎസ്ഇബി ബിൽ", category="bills", submission="api", fields=[
        {"key": "consumer_number", "type": "number", "required": True, "pattern": "[0-9]{13}", "ask_ml": "കൺസ്യൂമർ നമ്പർ?"},
        {"key": "payer_mobile", "type": "phone", "required": True, "ask_ml": "മൊബൈൽ?"},
        {"key": "confirm_amount", "type": "yesno", "required": True, "ask_ml": "?"}]),
}


class FakeDb:
    """Same methods as db.Db. `worker(db, job, n)` is called on every get_job to simulate the automation worker."""
    def __init__(self, svc="pdf", worker=None, citizens=None):
        self.svcs = [dict(SERVICES[svc])]
        self.citizens, self.cases, self.events, self.consents, self.jobs, self.prompts = list(citizens or []), {}, [], [], {}, {}
        self.worker, self.polls, self.order = worker, itertools.count(), []

    def services(self): return [dict(s) for s in self.svcs]
    def find_citizens(self, m): return [c for c in self.citizens if c.get("phone_masked") == m]

    def add_citizen(self, row):
        row = dict(row, id=str(uuid.uuid4())); self.citizens.append(row); return row

    def add_case(self, row):
        row = dict(row, id=str(uuid.uuid4()), case_number="123456"); self.cases[row["id"]] = row; return row

    def get_case(self, cid): return self.cases[cid]
    def set_case(self, cid, **kw): self.cases[cid].update(kw)

    def event(self, cid, type, message, data=None):
        self.events.append(dict(case_id=cid, actor="voice", type=type, message=message, data=data or {}))

    def add_consent(self, cid, kind, text):
        self.order.append("consent:" + kind); self.consents.append(dict(case_id=cid, kind=kind, text=text, channel="phone"))

    def add_job(self, cid, kind, mode):
        self.order.append("job:" + kind)
        j = dict(id=str(uuid.uuid4()), case_id=cid, kind=kind, mode=mode, status="queued", result=None, error=None)
        self.jobs[j["id"]] = j; return dict(j)

    def get_job(self, jid):
        j = self.jobs[jid]
        if self.worker: self.worker(self, j, next(self.polls))
        return dict(j)

    def add_prompt(self, jid, kind, text="", media=None):
        p = dict(id=str(uuid.uuid4()), job_id=jid, kind=kind, prompt_text=text, prompt_text_ml=None, media_path=media, status="open", answer=None)
        self.prompts[p["id"]] = p; return p

    def open_prompts(self, jid): return [dict(p) for p in self.prompts.values() if p["job_id"] == jid and p["status"] == "open"]
    def answer_prompt(self, pid, a): self.prompts[pid].update(answer=a, status="answered")
    def download(self, path): return b"RIFFfake"

    def blob(self):
        return repr((self.events, self.consents, [c["data"] for c in self.cases.values()]))
