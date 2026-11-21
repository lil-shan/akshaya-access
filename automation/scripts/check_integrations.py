"""One harmless authenticated call per provider that has keys in ../.integrations.env. Prints OK/FAIL/SKIP only, never values.
Usage: .venv/bin/python scripts/check_integrations.py"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
import worker; worker.load_env()
import payments
from payments import env, requests

def razorpay():
    r = requests.get(payments.RZP + "/v1/payment_links", params={"count": 1}, auth=(env("RAZORPAY_KEY_ID"), env("RAZORPAY_KEY_SECRET")), timeout=30)
    return r.status_code == 200, f"HTTP {r.status_code}"
def eko():
    e = payments.Eko(); r = requests.get(f"{e.base}/user/account/balance/{env('EKO_USER_CODE')}", headers=e._h(), params={"initiator_id": env("EKO_INITIATOR_ID")}, timeout=30)
    j = r.json(); return r.status_code == 200 and j.get("status") == 0, f"HTTP {r.status_code}, eko status {j.get('status')}"
def digilocker():
    import digilocker_real as dl
    v, c = dl.pkce_pair(); u = dl.auth_url(env("DIGILOCKER_CLIENT_ID"), env("DIGILOCKER_REDIRECT_URI"), "chk", c)
    r = requests.get(u, allow_redirects=False, timeout=30)   # authorize page reachable; full OAuth needs a human consent
    return r.status_code < 500, f"authorize endpoint HTTP {r.status_code} (consent flow not exercised)"

CHECKS = [("razorpay", ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"], razorpay),
          ("eko", ["EKO_DEVELOPER_KEY", "EKO_ACCESS_KEY", "EKO_INITIATOR_ID", "EKO_USER_CODE"], eko),
          ("digilocker", ["DIGILOCKER_CLIENT_ID", "DIGILOCKER_CLIENT_SECRET", "DIGILOCKER_REDIRECT_URI"], digilocker)]
if __name__ == "__main__":
    bad = 0
    for name, keys, fn in CHECKS:
        miss = [k for k in keys if not env(k)]
        if miss: print(f"SKIP {name}: missing {', '.join(miss)} (names only)"); continue
        try: ok, note = fn()
        except Exception as e: ok, note = False, type(e).__name__
        print(("OK   " if ok else "FAIL ") + f"{name}: {note}"); bad += not ok
    sys.exit(1 if bad else 0)
