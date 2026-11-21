"""End-to-end against the real Supabase project: dummy citizen -> case -> job -> worker -> verify.
TEST-ONLY SHORTCUT: the OTP is read from the mock portal's local SMS log and the captcha from the mock's known-answer file.
This only works for the MOCK portal; real portals never expose these. Usage: python scripts/e2e_mock.py"""
import os, random, subprocess, sys, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
import worker; worker.load_env(); db = worker.Db().c
MOCK = ROOT / "mock_portals/edistrict"

def wait_for_catalogue(ids, tries=30):
    for _ in range(tries):
        have = {r["id"] for r in db.table("services").select("id").execute().data}
        if set(ids) <= have: return
        print("waiting for CRM seed of services:", sorted(set(ids) - have)); time.sleep(10)
    sys.exit("services not seeded yet (CRM agent) - re-run later")

def make_job(service_id, data, kind, mode):
    cit = db.table("citizens").insert({"full_name": "E2E Dummy Citizen", "phone_masked": "XXXXXX0000", "dob": "1980-01-01", "gender": "F"}).execute().data[0]
    case = db.table("cases").insert({"case_number": f"{random.randint(100000, 999999)}", "citizen_id": cit["id"], "service_id": service_id,
        "status": "ready", "channel": "crm", "data": data}).execute().data[0]
    db.table("consents").insert({"case_id": case["id"], "kind": "automation", "text": "E2E test consent (dummy data)", "channel": "crm"}).execute()
    job = db.table("automation_jobs").insert({"case_id": case["id"], "kind": kind, "mode": mode, "status": "queued"}).execute().data[0]
    return case, job

def answerer(job_id, stop):
    """Plays the citizen. Test-only shortcut, mock portal only."""
    while not stop.is_set():
        for p in db.table("job_prompts").select("*").eq("job_id", job_id).eq("status", "open").execute().data:
            ans = None
            if p["kind"] == "otp":
                lines = (MOCK / "sms.log").read_text().splitlines() if (MOCK / "sms.log").exists() else []
                ans = lines[-1].split()[-1] if lines else None
            elif p["kind"] == "captcha_audio" and (MOCK / "captcha_answer.txt").exists():
                ans = (MOCK / "captcha_answer.txt").read_text().strip()
            if ans: db.table("job_prompts").update({"answer": ans, "status": "answered", "answered_at": worker.now()}).eq("id", p["id"]).execute()
        time.sleep(1)

def get_job(job_id):
    """Poll read tolerant of a transient Supabase/network disconnect (retries, then raises)."""
    for i in range(4):
        try: return db.table("automation_jobs").select("*").eq("id", job_id).single().execute().data
        except Exception:
            if i == 3: raise
            time.sleep(2)

def run(service_id, data, kind, mode, with_answerer):
    case, job = make_job(service_id, data, kind, mode); stop = threading.Event()
    if with_answerer:
        (MOCK / "sms.log").unlink(missing_ok=True); threading.Thread(target=answerer, args=(job["id"], stop), daemon=True).start()
    w = subprocess.Popen([sys.executable, str(ROOT / "worker.py")], cwd=ROOT)
    try:
        for _ in range(120):
            j = get_job(job["id"])
            if j["status"] in ("succeeded", "failed", "cancelled"): break
            time.sleep(1)
    finally: stop.set(); stop_worker(w)
    check(j["status"] in ("succeeded", "failed", "cancelled"), f"{kind} job finished within 120s (stuck in status={j['status']}; a stray worker.py may be stealing jobs)")
    return case, j

def stop_worker(w):
    w.terminate()
    try: w.wait(10)
    except subprocess.TimeoutExpired: w.kill(); w.wait(5)

def stray_workers():
    out = subprocess.run(["pgrep", "-af", "^[^ ]*python[^ ]* [^ ]*worker\\.py"], capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if "pgrep" not in l]

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: sys.exit(1)

if __name__ == "__main__":
    wait_for_catalogue(["edistrict_income_certificate", "pmjjby_claim", "pmsby_claim"])
    # mock portal job
    case, j = run("edistrict_income_certificate", {"applicant_name": "E2E Dummy Citizen", "dob": "1980-01-01", "mobile": "9000000000",
        "father_name": "Dummy Father", "address": "1 Test Road, Kochi", "annual_income": "90000", "income_source": "Daily wage", "purpose": "Scholarship"},
        "portal_fill", "mock", True)
    check(j["status"] == "succeeded", f"mock job succeeded (error={j['error']})")
    check(j["result"]["stopped_before_submit"] is True, "stopped_before_submit=true")
    check(not (MOCK / "SUBMITTED").exists(), "mock portal never received a submit")
    check(len(j["result"]["screenshots"]) >= 4, f"{len(j['result']['screenshots'])} screenshots stored")
    blob = str(db.table("case_events").select("*").eq("case_id", case["id"]).execute().data) + str(j["result"])
    otp = (MOCK / "sms.log").read_text().split()[-1]; cap = (MOCK / "captcha_answer.txt").read_text().strip()
    check(otp not in blob and cap not in blob, "no OTP/captcha values in case_events or result")
    ps = db.table("job_prompts").select("status,answer,kind").eq("job_id", j["id"]).execute().data
    check(all(p["answer"] is None for p in ps) and {"used"} <= {p["status"] for p in ps}, f"prompts used+nulled {[(p['kind'], p['status']) for p in ps]}")
    check(db.table("cases").select("status").eq("id", case["id"]).single().execute().data["status"] == "done", "case status done")
    # pdf jobs
    for sid in ("pmjjby_claim", "pmsby_claim"):
        case, j = run(sid, {"insured_name": "E2E Dummy Insured", "date_of_death": "2026-10-01", "claimant_name": "E2E Dummy Citizen",
            "claimant_ifsc": "SBIN0000001"}, "fill_pdf", "mock", False)
        check(j["status"] == "succeeded" and j["result"]["output_pdf"] == f"{case['id']}/{j['id']}/claim.pdf", f"{sid} pdf job succeeded")
        pdf = db.storage.from_("case-files").download(j["result"]["output_pdf"]); check(pdf[:4] == b"%PDF", f"{sid} claim.pdf downloaded from storage ({len(pdf)} bytes)")
    print("E2E OK")
