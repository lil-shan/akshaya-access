"""Full e2e against the real Supabase project with dummy data. Every row is tagged: citizens.full_name starts with 'E2E ',
cases.data._e2e = true. TEST-ONLY SHORTCUT: OTP/captcha answers are read from the mock portal's local files (mock only).
Cleanup: delete cases where data->>_e2e = 'true' and citizens where full_name like 'E2E %'. Usage: python scripts/e2e_all.py"""
import random, sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_mock as E
from e2e_mock import db, MOCK, check, worker

def make_job(service_id, data, kind, mode, consent="automation"):
    cit = db.table("citizens").insert({"full_name": "E2E Dummy Citizen", "phone_masked": "XXXXXX0000", "dob": "1980-01-01", "gender": "F"}).execute().data[0]
    case = db.table("cases").insert({"case_number": f"{random.randint(100000, 999999)}", "citizen_id": cit["id"], "service_id": service_id,
        "status": "ready", "channel": "crm", "data": dict(data, _e2e=True)}).execute().data[0]
    if consent: db.table("consents").insert({"case_id": case["id"], "kind": consent, "text": "E2E test consent (dummy data)", "channel": "crm"}).execute()
    return case, db.table("automation_jobs").insert({"case_id": case["id"], "kind": kind, "mode": mode, "status": "queued"}).execute().data[0]

_orig = E.make_job
def patched(service_id, data, kind, mode): return make_job(service_id, data, kind, mode, CONSENT[0])
E.make_job = patched; CONSENT = ["automation"]

CLAIM = {"insured_name": "E2E Dummy Insured", "insured_dob": "1970-01-01", "date_of_death": "2026-10-01", "cause_of_death": "Accident",
    "place_of_death": "Kochi", "insured_bank_account": "123456789012", "claimant_name": "E2E Dummy Citizen", "claimant_relationship": "Spouse",
    "claimant_dob": "1980-01-01", "claimant_address": "1 Test Road, Kochi", "claimant_mobile": "9000000000", "claimant_bank_name": "SBI Kochi",
    "claimant_account": "123456789012", "claimant_ifsc": "SBIN0000001"}
INCOME = {"applicant_name": "E2E Dummy Citizen", "dob": "1980-01-01", "mobile": "9000000000", "father_name": "Dummy Father",
    "address": "1 Test Road, Kochi", "annual_income": "90000", "income_source": "Daily wage", "purpose": "Scholarship"}

import json, re, glob, os
def dummy(f):
    """Plausible dummy value for a service.json field (E2E only)."""
    t, p = f["type"], f.get("pattern") or ""
    if t == "select": return f["options"][0]
    if t == "yesno": return "yes"
    if t == "date": return "1990-01-01"
    if t == "phone": return "9000000000"
    if t == "ifsc": return "SBIN0000001"
    if t == "account_number": return "123456789012"
    m = re.search(r"\{(\d+)(?:,\d+)?\}", p)
    if p and m: return "1234567890123"[:int(m.group(1))] if "[0-9]" in p else "A" * int(m.group(1))
    return "10" if t == "number" else f"E2E {f['key']}"

def upsert_missing_services(ids):
    """Self-contained: create services rows from portals/<id>/service.json when the orchestrator has not seeded them yet (existing rows untouched)."""
    have = {r["id"] for r in db.table("services").select("id").execute().data}
    for sid in ids:
        if sid in have: continue
        d = json.load(open(E.ROOT / "portals" / sid / "service.json"))
        db.table("services").insert({k: d[k] for k in ("id", "name", "name_ml", "category", "tier", "submission", "fields", "documents", "fee", "active", "notes")}).execute()
        print("INFO inserted services row", sid)

NEW_MOCK = ["edistrict_nativity_certificate", "edistrict_residence_certificate", "edistrict_community_certificate", "edistrict_relationship_certificate", "ksmart_birth_certificate", "ration_card_add_member"]
NEW_PDF = ["pmfby_crop_loss", "pan_form49a_prep", "passport_prep", "epf_withdrawal_prep"]

if __name__ == "__main__":
    os.environ["MOCK_URL"] = "http://127.0.0.1:8791"   # own mock-portal port; never the user's
    upsert_missing_services(NEW_MOCK + NEW_PDF + ["voter_form8", "kwa_water_bill"])
    E.wait_for_catalogue(["edistrict_income_certificate", "pmjjby_claim", "pmsby_claim"])
    # 1. missing fields
    bad = {k: v for k, v in CLAIM.items() if k not in ("claimant_name", "claimant_ifsc")}; bad["claimant_account"] = "SECRET-bad"
    case, j = E.run("pmjjby_claim", bad, "fill_pdf", "mock", False)
    check(j["status"] == "failed" and j["error"] == "missing_fields: claimant_name,claimant_account,claimant_ifsc", f"missing-fields failure (error={j['error']})")
    check("SECRET-bad" not in str(db.table("case_events").select("*").eq("case_id", case["id"]).execute().data), "no field values in events")
    check(db.table("cases").select("status").eq("id", case["id"]).single().execute().data["status"] == "draft", "case back to draft")
    # 2. mock portal with spoken captcha
    case, j = E.run("edistrict_income_certificate", INCOME, "portal_fill", "mock", True)
    check(j["status"] == "succeeded", f"mock job succeeded (error={j['error']})")
    check(j["result"]["stopped_before_submit"] is True and not (MOCK / "SUBMITTED").exists(), "stopped before submit, mock never submitted")
    wav = db.storage.from_("case-files").download(f"{case['id']}/{j['id']}/captcha.wav")
    rate = struct.unpack("<I", wav[24:28])[0]
    print(f"INFO captcha.wav {len(wav)} bytes, {rate} Hz ({'spoken (Sarvam TTS)' if rate != 8000 else 'beep fallback'})")
    blob = str(db.table("case_events").select("*").eq("case_id", case["id"]).execute().data) + str(j["result"])
    check((MOCK / "captcha_answer.txt").read_text().strip() not in blob, "captcha value not logged")
    # 3. pdf for both claims
    for sid in ("pmjjby_claim", "pmsby_claim"):
        case, j = E.run(sid, CLAIM, "fill_pdf", "mock", False)
        check(j["status"] == "succeeded", f"{sid} pdf job succeeded (error={j['error']})")
        pdf = db.storage.from_("case-files").download(j["result"]["output_pdf"]); check(pdf[:4] == b"%PDF", f"{sid} claim.pdf in storage ({len(pdf)} bytes)")
    # 4. digilocker success and no consent
    CONSENT[0] = "digilocker"
    case, j = E.run("pmjjby_claim", CLAIM, "digilocker_fetch", "mock", False)
    check(j["status"] == "succeeded" and len(j["result"]["documents"]) == 3, f"digilocker succeeded (error={j['error']})")
    docs = db.table("documents").select("*").eq("case_id", case["id"]).eq("source", "digilocker").execute().data
    check(len(docs) == 3 and all(db.storage.from_("case-files").download(d["storage_path"])[:4] == b"%PDF" for d in docs), f"{len(docs)} digilocker documents rows + files")
    CONSENT[0] = None
    case, j = E.run("pmjjby_claim", CLAIM, "digilocker_fetch", "mock", False)
    check(j["status"] == "failed" and j["error"] == "missing_consent:digilocker", f"digilocker without consent fails (error={j['error']})")
    # 5. payments: KSEB bill fetch via Eko mock server, Razorpay SIMULATED paid, Eko mock pay
    import os, subprocess, threading, time, payments
    from e2e_mock import ROOT
    os.environ.update(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="", EKO_DEVELOPER_KEY="", EKO_ACCESS_KEY="", PAY_POLL_SECONDS="1", UPI_DEMO_VPA="", EKO_MOCK_URL=payments.EKO_MOCK)
    E.wait_for_catalogue(["kseb_bill_payment"]); mock = payments.start_eko_mock(); print("INFO Eko mock server on", payments.EKO_MOCK)
    try:
        KSEB = {"consumer_number": "1234567890123", "payer_mobile": "9000000000", "confirm_amount": "yes"}
        CONSENT[0] = None
        case, j = E.run("kseb_bill_payment", KSEB, "bbps_fetch", "mock", False)
        check(j["status"] == "succeeded" and j["result"]["amount_inr"] > 0 and j["result"]["sandbox"], f"bbps_fetch via {j['result'] and j['result'].get('provider')} (error={j['error']})")
        data = db.table("cases").select("data").eq("id", case["id"]).single().execute().data["data"]
        check(data["_bill"]["amount_inr"] == j["result"]["amount_inr"], "bill merged into cases.data._bill")
        amt = data["_bill"]["amount_inr"]
        def pay_when_pending():  # test-only: stands in for the citizen paying in their UPI app
            for _ in range(60):
                r = db.table("payments").select("reference").eq("case_id", case["id"]).execute().data
                if r: payments.sim_mark_paid(r[0]["reference"]); return
                time.sleep(1)
        def collect(consent_text, c_id=None, drop_bill=False):
            if consent_text:
                db.table("consents").insert({"case_id": case["id"], "kind": "payment", "text": consent_text, "channel": "crm"}).execute()
            jb = db.table("automation_jobs").insert({"case_id": case["id"], "kind": "payment_collect", "mode": "mock", "status": "queued"}).execute().data[0]
            w = subprocess.Popen([sys.executable, str(ROOT / "worker.py")], cwd=ROOT, env=dict(os.environ))
            try:
                for _ in range(90):
                    jj = db.table("automation_jobs").select("*").eq("id", jb["id"]).single().execute().data
                    if jj["status"] in ("succeeded", "failed"): return jj
                    time.sleep(1)
            finally: w.terminate()
        # missing consent
        jj = collect(None); check(jj["status"] == "failed" and jj["error"] == "missing_consent:payment", f"payment_collect without consent fails (error={jj['error']})")
        # amount mismatch
        db.table("consents").insert({"case_id": case["id"], "kind": "payment", "text": f"I agree to pay Rs {amt + 1}", "channel": "crm"}).execute()
        jj = collect(None); check(jj["status"] == "failed" and jj["error"] == "amount_mismatch", f"amount mismatch fails (error={jj['error']})")
        check(not db.table("payments").select("id").eq("case_id", case["id"]).execute().data, "no payment row created on mismatch")
        db.table("consents").delete().eq("case_id", case["id"]).eq("kind", "payment").execute()
        # happy path
        threading.Thread(target=pay_when_pending, daemon=True).start()
        jj = collect(f"I agree to pay Rs {amt} for my KSEB bill (test mode)")
        check(jj["status"] == "succeeded", f"payment_collect succeeded (error={jj['error']})")
        pays = db.table("payments").select("*").eq("case_id", case["id"]).execute().data
        check(len(pays) == 1 and pays[0]["status"] == "confirmed" and pays[0]["provider"] == "razorpay_test" and pays[0]["amount_inr"] == amt, "payments row confirmed")
        check(jj["result"]["eko_reference"] == jj["result"]["eko"]["reference"] and jj["result"]["payment_provider"] == "SIMULATED_RAZORPAY", f"Eko mock pay reference {jj['result']['eko']['reference']}, link {jj['result']['short_url']}")
        # v1.5 UPI QR demo: test marks the payments row confirmed (stands in for the CRM "Mark received" button)
        os.environ["UPI_DEMO_VPA"] = "test@upi"; db.table("payments").delete().eq("case_id", case["id"]).execute()
        def confirm_row():
            for _ in range(60):
                r = db.table("payments").select("id").eq("case_id", case["id"]).eq("provider", "upi_qr_demo").execute().data
                if r: db.table("payments").update({"status": "confirmed"}).eq("id", r[0]["id"]).execute(); return
                time.sleep(1)
        threading.Thread(target=confirm_row, daemon=True).start()
        jj = collect(f"I agree to pay Rs {amt} for my KSEB bill (demo)")
        check(jj["status"] == "succeeded" and jj["result"]["upi_uri"].startswith("upi://pay?pa=test@upi") and f"am={amt}.00" in jj["result"]["upi_uri"], f"upi_qr_demo job succeeded (error={jj['error']})")
        check(jj["result"]["eko_reference"], f"upi_qr_demo -> Eko mock reference {jj['result']['eko_reference']}")
        os.environ["UPI_DEMO_VPA"] = ""
        # missing _bill
        case2, j2 = E.run("kseb_bill_payment", KSEB, "payment_collect", "mock", False)
        check(j2["status"] == "failed" and j2["error"] == "missing_bill", f"payment_collect without _bill fails (error={j2['error']})")
        # v1.6: KWA water bill through the same Eko mock code path (water operator)
        E.wait_for_catalogue(["kwa_water_bill"]); CONSENT[0] = None
        KWA = {"consumer_number": "1234567890", "payer_mobile": "9000000000", "confirm_amount": "yes"}
        case, j = E.run("kwa_water_bill", KWA, "bbps_fetch", "mock", False)
        check(j["status"] == "succeeded" and j["result"]["amount_inr"] > 0, f"kwa_water_bill bbps_fetch via {j['result'] and j['result'].get('provider')} (error={j['error']})")
        amt = j["result"]["amount_inr"]; threading.Thread(target=pay_when_pending, daemon=True).start()
        jj = collect(f"I agree to pay Rs {amt} for my Kerala Water Authority bill (test mode)")
        check(jj["status"] == "succeeded" and jj["result"]["eko_reference"], f"kwa_water_bill payment_collect succeeded, Eko ref {jj['result'] and jj['result'].get('eko_reference')} (error={jj['error']})")
    finally:
        payments.stop_eko_mock(mock)
    # v1.6: one job per new mock-portal / pdf service (voter_form8 is replay-test only: tests/test_services_v16.py)
    for sid in NEW_MOCK:
        svc = json.load(open(E.ROOT / "portals" / sid / "service.json")); data = {f["key"]: dummy(f) for f in svc["fields"]}
        (MOCK / "SUBMITTED").unlink(missing_ok=True); CONSENT[0] = "automation"
        case, j = E.run(sid, data, "portal_fill", "mock", True)
        check(j["status"] == "succeeded" and j["result"]["stopped_before_submit"] and len(j["result"]["screenshots"]) >= 4 and not (MOCK / "SUBMITTED").exists(), f"{sid} mock job stopped before submit (error={j['error']})")
        blob = str(db.table("case_events").select("*").eq("case_id", case["id"]).execute().data) + str(j["result"])
        check((MOCK / "captcha_answer.txt").read_text().strip() not in blob, f"{sid} captcha value not logged")
    for sid in NEW_PDF:
        svc = json.load(open(E.ROOT / "portals" / sid / "service.json")); data = {f["key"]: dummy(f) for f in svc["fields"]}
        case, j = E.run(sid, data, "fill_pdf", "mock", False)
        check(j["status"] == "succeeded", f"{sid} pdf job succeeded (error={j['error']})")
        pdf = db.storage.from_("case-files").download(j["result"]["output_pdf"]); check(pdf[:4] == b"%PDF", f"{sid} sheet in storage ({len(pdf)} bytes)")
    print("INFO voter_form8: real-portal dry run, replay test only (pytest tests/test_services_v16.py)")
    print("E2E ALL OK")
