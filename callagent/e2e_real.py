"""Integration test against the REAL Supabase project with a REAL worker process (automation/worker.py).
Rows are tagged: citizens.full_name starts 'E2E ', cases.data._e2e=true. Test-only hooks (CALLAGENT_TEST_HOOKS=1) read the
mock portal's sms.log / captcha_answer.txt so the scripted citizen can 'receive' the OTP and 'hear' the captcha.
Run: .venv/bin/python e2e_real.py [income|pmjjby|kseb ...]"""
import os
import random
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ["CALLAGENT_TEST_HOOKS"] = "1"
import db as dbm
from call import MOCK, TextIO
from engine import Call

AUT = Path(__file__).resolve().parent.parent / "automation"
BY_TYPE = {"text": "E2E sample", "date": "12/03/1980", "number": "50000", "phone": "9876543210", "account_number": "123456789012",
           "ifsc": "SBIN0001234", "textarea": "E2E sample text", "email": "e2e@example.com", "yesno": "അതെ"}
OVERRIDE = {"consumer_number": "1234567890123", "date_of_death": "01/05/2026", "annual_income": "50000", "pincode": "682001"}
SCENARIOS = {  # name -> (category word, service word, service id, extra lines at the end)
    "income": ("certificates", "income", "edistrict_income_certificate"),
    "pmjjby": ("insurance", "PMJJBY", "pmjjby_claim"),
    "kseb": ("bills", "KSEB", "kseb_bill_payment"),
}


def script(svc, cat, word):
    lines = [cat, word, "E2E Caller " + str(random.randint(100, 999)), "അതെ"]
    for f in svc["fields"]:
        if f.get("source") == "citizen.full_name" or (f["key"] == "confirm_amount" and svc["submission"] == "api"):
            continue
        if not f.get("required"):
            lines.append("ഇല്ല"); continue
        if f["type"] == "select":
            lines.append("1"); continue
        lines += [OVERRIDE.get(f["key"]) or BY_TYPE.get(f["type"], "E2E sample"), "അതെ"]
    lines.append("അതെ")  # consent
    if svc["submission"] == "mock_portal":
        lines += ["{{SMS_OTP}}", "{{CAPTCHA_ANSWER}}"]
    if svc["submission"] == "api":
        lines.append("അതെ")  # confirm the read-back amount (payment consent)
    return lines


def auto_pay(db, stop):
    """Test-only: plays the citizen paying in their own UPI app against the SIMULATED Razorpay link."""
    sys.path.insert(0, str(AUT))
    import payments
    done = set()
    while not stop.is_set():
        for j in db.c.table("automation_jobs").select("id,result").eq("kind", "payment_collect").eq("status", "running").execute().data:
            u = (j.get("result") or {}).get("short_url", "")
            if "/simulated/" in u and j["id"] not in done:
                done.add(j["id"]); payments.sim_mark_paid(u.rsplit("/", 1)[1])
        stop.wait(2)


def main(names):
    dbm.load_env()
    db = dbm.Db()
    svcs = {s["id"]: s for s in db.services()}
    env = dict(os.environ, UPI_DEMO_VPA="", RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="", PAY_POLL_SECONDS="1")
    worker = subprocess.Popen([str(AUT / ".venv/bin/python"), "worker.py"], cwd=AUT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    stop = threading.Event(); threading.Thread(target=auto_pay, args=(dbm.Db(), stop), daemon=True).start()
    results = {}
    try:
        for n in names:
            cat, word, sid = SCENARIOS[n]
            lines = script(svcs[sid], cat, word)
            io = TextIO(lines)
            phone = "90000" + str(random.randint(10000, 99999))
            print(f"\n===== {n} ({sid}) =====", flush=True)
            case = Call(io, db, phone=phone, extra_data={"_e2e": True}, job_wait=300).run()
            jobs = db.c.table("automation_jobs").select("*").eq("case_id", case["id"]).order("created_at").execute().data
            events = db.c.table("case_events").select("*").eq("case_id", case["id"]).execute().data
            cons = db.c.table("consents").select("kind,channel").eq("case_id", case["id"]).execute().data
            blob = repr(events) + repr(db.get_case(case["id"]))
            secrets = set(re.findall(r"OTP is (\d+)", (MOCK / "sms.log").read_text())[-1:]) if n == "income" else set()
            if n == "income":
                secrets.add((MOCK / "captcha_answer.txt").read_text().strip())
            leak = [s for s in secrets if s and s in blob or any(s in t for _, t in io.transcript)]
            results[n] = [(j["kind"], j["status"], j.get("error"), (j.get("result") or {}).get("stopped_before_submit"),
                           (j.get("result") or {}).get("payment_status")) for j in jobs]
            print("JOBS", results[n], "CONSENTS", cons, "CASE", db.get_case(case["id"])["status"], "voice events", sum(e["actor"] == "voice" for e in events),
                  "SECRET LEAKS", len(leak), flush=True)
    finally:
        stop.set(); worker.terminate(); worker.wait(10)
    return results


if __name__ == "__main__":
    main(sys.argv[1:] or list(SCENARIOS))
