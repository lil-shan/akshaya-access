"""Automation worker: polls automation_jobs, runs pdf / mock_portal jobs. See contracts/crm.md "Job protocol".
Never submits on a portal, never solves captchas, never logs OTP/captcha values."""
import os, re, secrets, uuid, sys, time, socket, subprocess, urllib.request, datetime as dt
from pathlib import Path
HERE = Path(__file__).parent
BUCKET = "case-files"
PROMPT_TTL = 180  # seconds (contract: 3 min)
WORKER = f"worker-{os.getpid()}"

class InputTimeout(Exception): pass
class JobError(Exception): pass  # error string is stored verbatim (e.g. missing_consent:digilocker)
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()

def load_env():
    for f in (HERE / ".env", HERE.parent / ".cloud.env", HERE.parent / ".integrations.env"):
        if f.exists():
            for l in f.read_text().splitlines():
                if "=" in l and not l.startswith("#"):
                    k, v = l.split("=", 1); v = v.strip().strip('"\'')
                    if v: os.environ.setdefault(k.strip(), v)

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
    def consent_texts(self, case_id, kind): return [r["text"] or "" for r in self.c.table("consents").select("text").eq("case_id", case_id).eq("kind", kind).execute().data]
    def merge_case_data(self, case_id, extra):
        d = self.get_case(case_id).get("data") or {}; d.update(extra); self.c.table("cases").update({"data": d, "updated_at": now()}).eq("id", case_id).execute()
    def add_payment(self, row): return self.c.table("payments").insert(row).execute().data[0]["id"]
    def payment_status(self, pid): return self.c.table("payments").select("status").eq("id", pid).single().execute().data["status"]
    def set_payment(self, pid, **kw): self.c.table("payments").update(kw).eq("id", pid).execute()
    def get_citizen(self, cid): return self.c.table("citizens").select("*").eq("id", cid).single().execute().data
    def add_document(self, case_id, kind, path, source):
        self.c.table("documents").insert({"case_id": case_id, "kind": kind, "storage_path": path, "source": source}).execute()

def ask(db, job, kinds, timeout=PROMPT_TTL, poll=1.0, extra=None):
    """kinds: list of (kind, prompt_text, media_path). Opens one prompt per entry, returns (kind, answer) from the
    first one answered. The answer is used once: row set to used + answer nulled immediately. Timeout -> InputTimeout."""
    exp = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=timeout)).isoformat()
    ids = [db.add_prompt({"job_id": job["id"], "kind": k, "prompt_text": t, "media_path": m, "status": "open", "expires_at": exp}) for k, t, m in kinds]
    db.set_job(job["id"], status="waiting_input"); db.set_case(job["case_id"], "waiting_citizen")
    db.event(job["case_id"], "waiting_input", "Waiting for citizen: " + ", ".join(k for k, _, _ in kinds))
    end = time.time() + timeout
    while time.time() < end:
        if extra and (v := extra()) is not None:  # out-of-band answer (e.g. DigiLocker callback); never logged
            for o in ids: db.set_prompt(o, status="cancelled", answer=None)
            db.set_job(job["id"], status="running"); db.set_case(job["case_id"], "running")
            db.event(job["case_id"], "input_received", "Citizen consent callback received (value not logged)"); return "callback", v
        for pid, (k, _, _) in zip(ids, kinds):
            p = db.get_prompt(pid)
            if p["status"] == "answered" and p.get("answer"):
                ans = p["answer"]
                db.set_prompt(pid, answer=None, status="used")
                for o in ids:
                    if o != pid: db.set_prompt(o, status="cancelled", answer=None)
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
    cit = db.get_citizen(case["citizen_id"]); docs = []; source = "SIMULATED_DIGILOCKER"
    import digilocker_real as dl
    if dl.live():
        source = "DIGILOCKER_SANDBOX"; verifier, challenge = dl.pkce_pair(); state = secrets.token_urlsafe(16)
        cb = dl.Callback(os.environ["DIGILOCKER_REDIRECT_URI"], state)
        try:
            url = dl.auth_url(os.environ["DIGILOCKER_CLIENT_ID"], os.environ["DIGILOCKER_REDIRECT_URI"], state, challenge)
            kind, v = ask(db, job, [("confirm", "Open this DigiLocker (sandbox) link and give consent: " + url, None)], timeout=600, extra=cb.poll)
            try: code = v if kind == "callback" else dl.parse_callback(v, state)
            except ValueError as e: raise JobError(f"digilocker_{e}")
        finally: cb.close()
        fetched = dl.fetch_documents(code, verifier); code = verifier = None
    else: fetched = digilocker_sim.fetch(cit.get("full_name") or "Dummy Citizen", str(cit.get("dob") or ""))
    for kind, name, data in fetched:
        path = f"{case['id']}/{job['id']}/{name}"
        db.upload(path, data, "application/pdf"); db.add_document(case["id"], kind, path, "digilocker"); docs.append({"kind": kind, "path": path})
    db.event(case["id"], "digilocker_fetched", f"Fetched {len(docs)} documents ({source}, sandbox/dummy data)", {"paths": [d["path"] for d in docs]})
    return {"documents": docs, "source": source, "summary": f"Fetched {len(docs)} DigiLocker documents ({source})."}

BILLERS = {"kseb_bill_payment": "KSEB", "kwa_water_bill": "Kerala Water Authority"}
def run_bbps_fetch(db, job, case, svc=None):
    import payments
    d = case.get("data") or {}; sid = case.get("service_id") or (svc or {}).get("id")
    pats = {f["key"]: (f.get("pattern") or "").strip("^$") for f in (svc or {}).get("fields") or [] if f["key"] in ("consumer_number", "payer_mobile")}
    pats = {"consumer_number": r"[0-9]{13}", "payer_mobile": r"[0-9]{10}", **{k: v for k, v in pats.items() if v}}
    bad = [k for k, pat in pats.items() if not re.fullmatch(pat, str(d.get(k) or ""))]
    if bad: raise JobError("missing_fields: " + ",".join(bad))
    eko = payments.Eko(); mock = None if eko.live else payments.start_eko_mock(eko.base)
    try: bill = eko.fetch_bill(str(d["consumer_number"]), str(d["payer_mobile"]), sid)
    finally:
        payments.stop_eko_mock(mock)
    db.merge_case_data(case["id"], {"_bill": bill}); db.event(case["id"], "bill_fetched", f"Bill fetched via {bill['provider']}: Rs {bill['amount_inr']} due {bill['due_date']}", {"amount_inr": bill["amount_inr"]})
    return dict(bill, summary=f"Bill Rs {bill['amount_inr']} fetched via {bill['provider']} (sandbox).")

def consent_amount_ok(texts, amount):
    """Consent text must read back the amount as 'Rs 2870' / '₹2,870' / 'INR 2870'."""
    for t in texts:
        for m in re.findall(r"(?:₹|Rs\.?|INR)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", t):
            if float(m.replace(",", "")) == float(amount): return True
    return False

def run_payment_collect(db, job, case, poll=None, timeout=900):
    import payments
    d = case.get("data") or {}; bill = d.get("_bill")
    if not bill: raise JobError("missing_bill")
    texts = db.consent_texts(case["id"], "payment")
    if not texts: raise JobError("missing_consent:payment")
    amt = bill["amount_inr"]
    if not consent_amount_ok(texts, amt): raise JobError("amount_mismatch")
    poll = poll or float(os.environ.get("PAY_POLL_SECONDS") or 5); prov = payments.select_provider()
    if prov == "upi_qr_demo":
        pid = str(uuid.uuid4()); label = "UPI_QR_DEMO"
        uri = payments.upi_uri(payments.env("UPI_DEMO_VPA"), payments.env("UPI_DEMO_NAME"), amt, case.get("case_number"), pid)
        db.add_payment({"id": pid, "case_id": case["id"], "provider": "upi_qr_demo", "amount_inr": amt, "status": "pending", "reference": pid})
        db.set_job(job["id"], result={"upi_uri": uri, "payment_provider": label, "amount_inr": amt})
        db.event(case["id"], "payment_link", f"UPI QR demo payment created for Rs {amt} (DEMO ONLY); waiting for a CRM user to mark it received")
        url, status = uri, lambda: db.payment_status(pid)
    else:
        rz = payments.Razorpay(); label = rz.label
        link = rz.create_link(amt, f"case-{case.get('case_number')}", f"{BILLERS.get(case.get('service_id'), 'Utility')} bill payment Rs {amt} (test mode)")
        pid = db.add_payment({"case_id": case["id"], "provider": "razorpay_test", "amount_inr": amt, "status": "pending", "reference": link["id"]})
        db.set_job(job["id"], result={"short_url": link["short_url"], "payment_provider": label, "amount_inr": amt})
        db.event(case["id"], "payment_link", f"Payment link created ({label}) for Rs {amt}; citizen pays in their own UPI app", {"short_url": link["short_url"]})
        url, status = link["short_url"], lambda: rz.status(link["id"])
    end = time.time() + timeout
    while time.time() < end:
        st = status()
        if st in ("paid", "confirmed"): break
        if st in ("expired", "cancelled", "failed"):
            db.set_payment(pid, status="failed"); raise JobError("payment_failed" if prov == "upi_qr_demo" else f"payment_{st}")
        time.sleep(poll)
    else: db.set_payment(pid, status="failed"); raise JobError("payment_timeout")
    db.set_payment(pid, status="confirmed"); db.event(case["id"], "payment_confirmed", f"Payment confirmed ({label})")
    eko = payments.Eko(); mock = None if eko.live else payments.start_eko_mock(eko.base)
    try: pay = eko.pay_bill(str(d["consumer_number"]), str(d["payer_mobile"]), amt, bill, case.get("service_id"))
    except Exception as e: db.event(case["id"], "bill_pay_failed", "Payment taken but bill-pay failed; needs manual refund/retry"); raise JobError(f"bill_pay_failed_after_payment:{e}"[:200])
    finally:
        payments.stop_eko_mock(mock)
    db.event(case["id"], "bill_paid", f"Bill paid via {pay['provider']} (sandbox), ref {pay['reference']}")
    return {("upi_uri" if prov == "upi_qr_demo" else "short_url"): url, "payment_provider": label, "amount_inr": amt, "payment_status": "confirmed", "eko": pay, "eko_reference": pay["reference"], "bill_provider": pay["provider"],
            "summary": f"Paid Rs {amt}: {label} confirmed, bill paid via {pay['provider']} ref {pay['reference']} (sandbox/test)."}

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

MOCK_KINDS = {"edistrict_income_certificate": "income", "edistrict_nativity_certificate": "nativity", "edistrict_residence_certificate": "residence",
              "edistrict_community_certificate": "community", "edistrict_relationship_certificate": "relationship",
              "ksmart_birth_certificate": "birth", "ration_card_add_member": "ration"}
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
            kind = MOCK_KINDS.get(svc["id"], "income"); pg.goto(url + "/?kind=" + kind); pg.fill("#mobile", str(data.get("mobile") or "9000000000"))
            pg.click("#send-otp"); db.event(cid, "step", "Mobile number entered, OTP requested from mock portal"); shot(pg, "01-otp-page")
            _, otp = ask(db, job, [("otp", "The mock portal sent an OTP by SMS to your phone. Please read it out.", None)])
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
    return {"screenshots": shots, "output_pdf": None, "stopped_before_submit": True, "summary": f"Mock portal ({svc['id']}) filled; stopped at review page. Nothing submitted."}

def run_portal_dry(db, job, case, svc):
    """Real-portal dry run (contract v1.2): needs consent 'portal_dry_run' and job mode 'dry_run'. Never submits. See dry_run.py."""
    import dry_run
    from playwright.sync_api import sync_playwright
    if job.get("mode") != "dry_run": raise JobError("mode_not_dry_run")
    if not db.has_consent(case["id"], "portal_dry_run"): raise JobError("missing_consent:portal_dry_run")
    cid, shots = case["id"], []
    def shot(pg, name):
        p = f"{cid}/{job['id']}/{name}.png"; db.upload(p, pg.screenshot(full_page=True), "image/png"); shots.append(p); db.add_document(cid, "screenshot", p, "screenshot")
    spec = dry_run.PORTALS[svc["id"]]
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True); ctx = b.new_context(user_agent=spec["ua"]) if spec.get("ua") else b.new_context(); pg = ctx.new_page()
        structs = []
        try: r = dry_run.run_dry(pg, db, job, case, svc["id"], shot, ask, base_url=os.environ.get("DRY_RUN_BASE_URL"), structs=structs)
        except dry_run.AbortRun as e: db.set_job(job["id"], result={"page_structures": structs, "screenshots": shots}); raise JobError(f"aborted:{e}")
        finally: b.close()
    db.event(cid, "stopped_before_submit", f"Dry run ended ({r['stopped_reason']}); nothing submitted")
    return {"screenshots": shots, "output_pdf": None, "stopped_before_submit": True, "stopped_reason": r["stopped_reason"], "page_structures": r["page_structures"],
            "summary": f"Dry run of {svc['id']} on the real portal stopped at: {r['stopped_reason']}. Nothing submitted."}

def process(db, job):
    case = db.get_case(job["case_id"]); svc = db.get_service(case["service_id"])
    sub = svc["submission"]; prior = case["status"]; db.set_case(case["id"], "running"); db.event(case["id"], "job_started", f"Job {job['kind']} ({sub}) started")
    try:
        bad = [] if job["kind"] in ("digilocker_fetch", "bbps_fetch") else missing_fields(svc.get("fields"), case.get("data") or {})
        if bad:
            err = "missing_fields: " + ",".join(bad)
            db.set_job(job["id"], status="failed", error=err, finished_at=now()); db.set_case(case["id"], "draft")
            db.event(case["id"], "job_failed", f"Job failed: {err}"); return
        if job["kind"] == "digilocker_fetch": res = run_digilocker(db, job, case)
        elif job["kind"] == "bbps_fetch": res = run_bbps_fetch(db, job, case, svc)
        elif job["kind"] == "payment_collect": res = run_payment_collect(db, job, case)
        elif sub == "pdf": res = run_pdf(db, job, case, svc)
        elif sub == "mock_portal": res = run_mock(db, job, case, svc)
        elif sub == "portal_dry_run": res = run_portal_dry(db, job, case, svc)
        else: raise RuntimeError(f"unsupported submission {sub}")
    except Exception as e:
        err = "citizen_input_timeout" if isinstance(e, InputTimeout) else str(e) if isinstance(e, JobError) else f"{type(e).__name__}: {e}"[:300]
        db.set_job(job["id"], status="failed", error=err, finished_at=now()); db.set_case(case["id"], "failed")
        db.event(case["id"], "job_failed", f"Job failed: {err}"); return
    db.set_job(job["id"], status="succeeded", result=res, finished_at=now()); db.set_case(case["id"], prior if job["kind"] in ("digilocker_fetch", "bbps_fetch") else "done")
    db.event(case["id"], "job_succeeded", res["summary"])

def loop(db, once=False):
    while True:
        for job in db.queued_jobs():
            try: svc = db.get_service(db.get_case(job["case_id"])["service_id"])
            except Exception: continue
            if svc["submission"] == "api" and job["kind"] not in ("digilocker_fetch", "bbps_fetch", "payment_collect"): continue
            if db.claim(job["id"]): process(db, job)
        if once: return
        time.sleep(2)

if __name__ == "__main__":
    load_env(); sys.path.insert(0, str(HERE)); print("worker started", WORKER, flush=True); loop(Db(), once="--once" in sys.argv)
