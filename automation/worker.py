"""Automation worker: polls automation_jobs, runs pdf / mock_portal jobs. See contracts/crm.md "Job protocol".
Never submits on a portal, never solves captchas, never logs OTP/captcha values."""
import os, sys, time, socket, subprocess, urllib.request, datetime as dt
from pathlib import Path
HERE = Path(__file__).parent
BUCKET = "case-files"
PROMPT_TTL = 180  # seconds (contract: 3 min)
WORKER = f"worker-{os.getpid()}"

class InputTimeout(Exception): pass
class JobError(Exception): pass  # error string is stored verbatim (e.g. missing_consent:digilocker)
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()

def load_env():
    for f in (HERE / ".env", HERE.parent / ".cloud.env"):
        if f.exists():
            for l in f.read_text().splitlines():
                if "=" in l and not l.startswith("#"):
                    k, v = l.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"\''))

class Db:
    """Thin wrapper over supabase-py (service role). Tests substitute a fake with the same methods."""
    def __init__(self):
        from supabase import create_client
        self.c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    def queued_jobs(self): return self.c.table("automation_jobs").select("*").eq("status", "queued").order("created_at").execute().data
    def claim(self, job_id):
        r = self.c.table("automation_jobs").update({"status": "running", "worker": WORKER, "started_at": now()}).eq("id", job_id).eq("status", "queued").execute()
        return bool(r.data)
    def get_case(self, case_id): return self.c.table("cases").select("*").eq("id", case_id).single().execute().data
    def get_service(self, sid): return self.c.table("services").select("*").eq("id", sid).single().execute().data
    def set_job(self, job_id, **kw): self.c.table("automation_jobs").update(kw).eq("id", job_id).execute()
    def set_case(self, case_id, status): self.c.table("cases").update({"status": status, "updated_at": now()}).eq("id", case_id).execute()
    def event(self, case_id, type, message, data=None):
        self.c.table("case_events").insert({"case_id": case_id, "actor": "automation", "type": type, "message": message, "data": data or {}}).execute()
    def add_prompt(self, row): return self.c.table("job_prompts").insert(row).execute().data[0]["id"]
    def get_prompt(self, pid): return self.c.table("job_prompts").select("*").eq("id", pid).single().execute().data
    def set_prompt(self, pid, **kw): self.c.table("job_prompts").update(kw).eq("id", pid).execute()
    def upload(self, path, data, ctype):
        self.c.storage.from_(BUCKET).upload(path, data, {"content-type": ctype, "upsert": "true"})
    def has_consent(self, case_id, kind): return bool(self.c.table("consents").select("id").eq("case_id", case_id).eq("kind", kind).limit(1).execute().data)
    def get_citizen(self, cid): return self.c.table("citizens").select("*").eq("id", cid).single().execute().data
    def add_document(self, case_id, kind, path, source):
        self.c.table("documents").insert({"case_id": case_id, "kind": kind, "storage_path": path, "source": source}).execute()

def ask(db, job, kinds, timeout=PROMPT_TTL, poll=1.0):
    """kinds: list of (kind, prompt_text, media_path). Opens one prompt per entry, returns (kind, answer) from the
    first one answered. The answer is used once: row set to used + answer nulled immediately. Timeout -> InputTimeout."""
    exp = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=timeout)).isoformat()
    ids = [db.add_prompt({"job_id": job["id"], "kind": k, "prompt_text": t, "media_path": m, "status": "open", "expires_at": exp}) for k, t, m in kinds]
    db.set_job(job["id"], status="waiting_input"); db.set_case(job["case_id"], "waiting_citizen")
    db.event(job["case_id"], "waiting_input", "Waiting for citizen: " + ", ".join(k for k, _, _ in kinds))
    end = time.time() + timeout
    while time.time() < end:
        for pid, (k, _, _) in zip(ids, kinds):
            p = db.get_prompt(pid)
            if p["status"] == "answered" and p.get("answer"):
                ans = p["answer"]
                db.set_prompt(pid, answer=None, status="used")
                for o in ids:
                    if o != pid: db.set_prompt(o, status="cancelled")
                db.set_job(job["id"], status="running"); db.set_case(job["case_id"], "running")
                db.event(job["case_id"], "input_received", f"Citizen answered {k} (value not logged)")
                return k, ans
        time.sleep(poll)
    for pid in ids: db.set_prompt(pid, status="expired")
    raise InputTimeout("citizen_input_timeout")

def missing_fields(fields, data):
    """Contract v1.1: keys (never values) of required fields that are empty, plus fields whose value fails `pattern`."""
    import re
    bad = []
    for f in fields or []:
        v = data.get(f["key"]); empty = v is None or str(v).strip() == ""
        if empty and f.get("required"): bad.append(f["key"])
        elif not empty and f.get("pattern") and not re.fullmatch(f["pattern"], str(v)): bad.append(f["key"])
    return bad

def run_digilocker(db, job, case):
    import digilocker_sim
    if not db.has_consent(case["id"], "digilocker"): raise JobError("missing_consent:digilocker")
    cit = db.get_citizen(case["citizen_id"]); docs = []
    for kind, name, data in digilocker_sim.fetch(cit.get("full_name") or "Dummy Citizen", str(cit.get("dob") or "")):
        path = f"{case['id']}/{job['id']}/{name}"
        db.upload(path, data, "application/pdf"); db.add_document(case["id"], kind, path, "digilocker"); docs.append({"kind": kind, "path": path})
    db.event(case["id"], "digilocker_fetched", f"Fetched {len(docs)} documents (SIMULATED_DIGILOCKER, dummy data)", {"paths": [d["path"] for d in docs]})
    return {"documents": docs, "source": "SIMULATED_DIGILOCKER", "summary": f"Fetched {len(docs)} dummy DigiLocker documents (simulated)."}

def run_pdf(db, job, case, svc):
    import pdf_filler
    path = f"{case['id']}/{job['id']}/claim.pdf"
    db.upload(path, pdf_filler.fill(svc["id"], case.get("data") or {}, case.get("case_number", ""), job["id"]), "application/pdf")
    db.add_document(case["id"], "claim_pdf", path, "generated")
    db.event(case["id"], "pdf_generated", f"Generated {svc['id']} claim PDF with checklist", {"path": path})
    return {"screenshots": [], "output_pdf": path, "stopped_before_submit": True, "summary": "Claim PDF + checklist generated (nothing submitted)."}

def mock_url():
    url = os.environ.get("MOCK_URL") or "http://127.0.0.1:8765"
    host, port = url.split("//")[1].split(":")[0], int(url.rsplit(":", 1)[1].strip("/"))
    try: socket.create_connection((host, port), 1).close(); return url, None
    except OSError:
        proc = subprocess.Popen([sys.executable, str(HERE / "mock_portals/edistrict/server.py"), str(port)]); time.sleep(1); return url, proc

def run_mock(db, job, case, svc):
    from playwright.sync_api import sync_playwright
    url, proc = mock_url(); shots = []; cid = case["id"]; base = f"{cid}/{job['id']}"
    def shot(pg, name):
        p = f"{base}/{name}.png"; db.upload(p, pg.screenshot(full_page=True), "image/png"); shots.append(p)
        db.add_document(cid, "screenshot", p, "screenshot")
    data = case.get("data") or {}
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True); pg = b.new_page()
            pg.goto(url + "/"); pg.fill("#mobile", str(data.get("mobile") or "9000000000"))
            pg.click("#send-otp"); db.event(cid, "step", "Mobile number entered, OTP requested from mock portal"); shot(pg, "01-otp-page")
            _, otp = ask(db, job, [("otp", "The e-District (mock) portal sent an OTP by SMS to your phone. Please read it out.", None)])
            pg.fill("#otp", otp); otp = None; pg.click("#verify-otp"); pg.wait_for_load_state()
            if "/captcha" not in pg.url: raise RuntimeError("portal rejected the OTP")
            db.event(cid, "step", "OTP accepted"); shot(pg, "02-captcha-page")
            audio = pg.request.get(url + "/captcha.wav").body(); img = pg.request.get(url + "/captcha.png").body()
            ap, ip = f"{base}/captcha.wav", f"{base}/captcha.png"
            db.upload(ap, audio, "audio/wav"); db.upload(ip, img, "image/png")
            _, cap = ask(db, job, [("captcha_audio", "Listen to the audio captcha and say the digits you hear.", ap),
                                   ("captcha_image", "Read the digits shown in the captcha image.", ip)])
            pg.fill("#captcha", cap); cap = None; pg.click("#verify-captcha"); pg.wait_for_load_state()
            if "/form" not in pg.url: raise RuntimeError("portal rejected the captcha")
            db.event(cid, "step", "Captcha accepted")
            filled = []
            for el in pg.query_selector_all("form [name]"):
                k = el.get_attribute("name"); v = data.get(k)
                if v in (None, ""): continue
                (pg.select_option if el.evaluate("e=>e.tagName") == "SELECT" else pg.fill)(f"[name={k}]", str(v)); filled.append(k)
            db.event(cid, "step", f"Filled {len(filled)} form fields", {"fields": filled}); shot(pg, "03-form-filled")
            pg.click("#to-review"); pg.wait_for_load_state(); shot(pg, "04-review")
            assert pg.query_selector("#final-submit"), "review page missing"
            db.event(cid, "stopped_before_submit", "Reached review page; Submit deliberately NOT clicked")
            b.close()
    finally:
        if proc: proc.terminate()
    return {"screenshots": shots, "output_pdf": None, "stopped_before_submit": True, "summary": "Mock e-District income certificate filled; stopped at review page."}

def process(db, job):
    case = db.get_case(job["case_id"]); svc = db.get_service(case["service_id"])
    sub = svc["submission"]; prior = case["status"]; db.set_case(case["id"], "running"); db.event(case["id"], "job_started", f"Job {job['kind']} ({sub}) started")
    try:
        bad = [] if job["kind"] == "digilocker_fetch" else missing_fields(svc.get("fields"), case.get("data") or {})
        if bad:
            err = "missing_fields: " + ",".join(bad)
            db.set_job(job["id"], status="failed", error=err, finished_at=now()); db.set_case(case["id"], "draft")
            db.event(case["id"], "job_failed", f"Job failed: {err}"); return
        if job["kind"] == "digilocker_fetch": res = run_digilocker(db, job, case)
        elif sub == "pdf": res = run_pdf(db, job, case, svc)
        elif sub == "mock_portal": res = run_mock(db, job, case, svc)
        elif sub == "portal_dry_run": raise RuntimeError("portal_dry_run is not implemented yet")
        else: raise RuntimeError(f"unsupported submission {sub}")
    except Exception as e:
        err = "citizen_input_timeout" if isinstance(e, InputTimeout) else str(e) if isinstance(e, JobError) else f"{type(e).__name__}: {e}"[:300]
        db.set_job(job["id"], status="failed", error=err, finished_at=now()); db.set_case(case["id"], "failed")
        db.event(case["id"], "job_failed", f"Job failed: {err}"); return
    db.set_job(job["id"], status="succeeded", result=res, finished_at=now()); db.set_case(case["id"], prior if job["kind"] == "digilocker_fetch" else "done")
    db.event(case["id"], "job_succeeded", res["summary"])

def loop(db, once=False):
    while True:
        for job in db.queued_jobs():
            try: svc = db.get_service(db.get_case(job["case_id"])["service_id"])
            except Exception: continue
            if svc["submission"] == "api" and job["kind"] != "digilocker_fetch": continue
            if db.claim(job["id"]): process(db, job)
        if once: return
        time.sleep(2)

if __name__ == "__main__":
    load_env(); sys.path.insert(0, str(HERE)); print("worker started", WORKER, flush=True); loop(Db(), once="--once" in sys.argv)
