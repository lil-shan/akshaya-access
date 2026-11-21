#!/usr/bin/env python3
"""FOR THE HUMAN OPERATOR ONLY. Queues a dry-run job (mode 'dry_run') for a case, then tells you which CRM prompts to answer.
Opens the REAL portal via the worker and sends a REAL OTP to YOUR phone. Nothing is ever submitted.
Refuses unless --i-am-the-citizen is given and stdin is a TTY. Requires consent kind='portal_dry_run' on the case."""
import sys, os, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
ap = argparse.ArgumentParser(); ap.add_argument("case_id"); ap.add_argument("--i-am-the-citizen", action="store_true")
a = ap.parse_args()
if not a.i_am_the_citizen or not sys.stdin.isatty():
    sys.exit("Refusing: this opens a REAL portal and sends a REAL OTP. Run it yourself in a terminal with --i-am-the-citizen (the citizen must be you, using your own phone).")
import worker; worker.load_env(); db = worker.Db()
case = db.get_case(a.case_id); svc = db.get_service(case["service_id"])
if svc["submission"] != "portal_dry_run": sys.exit(f"Service {svc['id']} is not a portal_dry_run service")
if not db.has_consent(case["id"], "portal_dry_run"): sys.exit("Missing consent kind='portal_dry_run' on this case (record it in the CRM first).")
bad = worker.missing_fields(svc.get("fields"), case.get("data") or {})
if bad: sys.exit("Case is missing fields: " + ",".join(bad))
print(f"About to queue a dry run of {svc['id']} on the REAL portal. A real OTP goes to YOUR phone. Nothing will be submitted.")
if input("Type YES to continue: ").strip() != "YES": sys.exit("Cancelled.")
row = db.c.table("automation_jobs").insert({"case_id": case["id"], "kind": "portal_fill", "mode": "dry_run", "status": "queued"}).execute().data[0]
print(f"Queued job {row['id']}. Make sure the worker is running (python worker.py). Then answer these in the CRM, in order, each within 3 minutes:")
print("  1. field   'Mobile number registered for this login'  (your own number; used once, never stored)")
if svc["id"] == "thuna_lost_property": print("  2. field   'Password for this portal login'  (used once, never stored)")
print("  -  captcha_audio / captcha_image: ECI offers audio (listen and type); Thuna is image only")
print("  -  otp: the SMS code sent to your phone")
print("The worker stops at the last preview, screenshots it, logs out. If the portal asks for Aadhaar, the run stops there.")
