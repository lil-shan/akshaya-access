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

if __name__ == "__main__":
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
    print("E2E ALL OK")
