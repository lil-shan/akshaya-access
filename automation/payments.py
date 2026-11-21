"""Provider adapters (contract v1.3): Eko EPS UAT BBPS + Razorpay test-mode Payment Links.
Keys come from env (loaded from ../.integrations.env); NEVER printed or logged. Empty keys -> clearly labelled mock/simulated mode.
Eko: docs developers.eko.in (auth page): headers developer_key, secret-key = base64(HMAC-SHA256(timestamp_ms, base64(access_key))),
secret-key-timestamp (13-digit ms). UAT base https://staging.eko.in/ekoapi/v3 . Paths/fixtures taken from @ekoindia/eps-mock-server."""
import base64, hashlib, hmac, json, os, socket, subprocess, time, uuid, datetime as dt
from pathlib import Path
from urllib.parse import urlencode, quote
import requests

HERE = Path(__file__).parent
EKO_UAT = "https://staging.eko.in/ekoapi/v3"
EKO_MOCK = "http://127.0.0.1:4010"   # `PORT=4010 npx @ekoindia/eps-mock-server`
RZP = "https://api.razorpay.com"
def env(k): return (os.environ.get(k) or "").strip()

# ---------------- Eko ----------------
def eko_headers(developer_key, access_key, ts_ms=None):
    ts = str(ts_ms or int(time.time() * 1000))
    sk = base64.b64encode(hmac.new(base64.b64encode(access_key.encode()), ts.encode(), hashlib.sha256).digest()).decode()
    return {"developer_key": developer_key, "secret-key": sk, "secret-key-timestamp": ts}

def eko_live(): return bool(env("EKO_DEVELOPER_KEY") and env("EKO_ACCESS_KEY"))

def port_open(url):
    host, port = url.split("//")[1].split(":")[0], int(url.rsplit(":", 1)[1].strip("/"))
    try: socket.create_connection((host, port), 1).close(); return True
    except OSError: return False

def start_eko_mock(url=EKO_MOCK):
    """Starts the official local mock if not already up. Returns Popen or None (caller terminates it)."""
    if port_open(url): return None
    p = subprocess.Popen(["npx", "--yes", "@ekoindia/eps-mock-server"], env=dict(os.environ, PORT=url.rsplit(":", 1)[1].strip("/")),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(90):
        if port_open(url): return p
        time.sleep(1)
    p.terminate(); raise RuntimeError("eko_mock_unavailable")

class Eko:
    def __init__(self, base=None):
        self.live = eko_live(); self.base = base or env("EKO_BASE_URL") or (EKO_UAT if self.live else env("EKO_MOCK_URL") or EKO_MOCK)
        self.label = "EKO_UAT" if self.live else "EKO_MOCK_SERVER"
    def _h(self): return eko_headers(env("EKO_DEVELOPER_KEY"), env("EKO_ACCESS_KEY")) if self.live else {}
    def _common(self, mobile, client_ref):
        return {"initiator_id": env("EKO_INITIATOR_ID") or "9962981729", "user_code": env("EKO_USER_CODE") or "20810200",
                "client_ref_id": client_ref, "source_ip": "127.0.0.1", "confirmation_mobile_no": mobile, "sender_name": "Akshaya Access"}
    def operator_id(self, service_id=None):
        if service_id == "kwa_water_bill": return env("EKO_KWA_OPERATOR_ID") or "KWA-OPERATOR-ID-UNSET"   # water category; find via find_operator("water")
        return env("EKO_KSEB_OPERATOR_ID") or "KSEB-OPERATOR-ID-UNSET"   # find via GET /customer/payment/bbps/operators (name ~ Kerala State Electricity)
    def find_operator(self, needle="kerala"):
        r = requests.get(self.base + "/customer/payment/bbps/operators", headers=self._h(), params={"category": 8}, timeout=30).json()
        return [o for o in (r.get("param_attributes") or {}).get("list_elements", []) if needle in o.get("name", "").lower()]
    def fetch_bill(self, consumer_no, mobile, service_id=None):
        ref = uuid.uuid4().hex[:20]
        p = dict(self._common(mobile, ref), utility_acc_no=consumer_no, operator_id=self.operator_id(service_id))
        r = requests.get(self.base + "/customer/payment/bbps/bill", headers=self._h(), params=p, timeout=30).json()
        return parse_bill(r, ref, self.label)
    def pay_bill(self, consumer_no, mobile, amount_inr, bill, service_id=None):
        ref = uuid.uuid4().hex[:20]
        body = dict(self._common(mobile, ref), phone_operator_code=self.operator_id(service_id), utility_acc_no=consumer_no, amount=int(amount_inr),
                    utilitycustomername=bill.get("customer_name", ""), category=8, communication=0)
        r = requests.post(self.base + "/customer/payment/bbps", headers=dict(self._h(), **{"Content-Type": "application/x-www-form-urlencoded"}),
                          data=urlencode(body), timeout=60).json()
        return parse_pay(r, ref, self.label)

def parse_bill(r, ref, label):
    d = r.get("data") or {}
    if r.get("status") != 0 or "amount" not in d: raise RuntimeError(f"bill_fetch_failed:{r.get('status')}")
    due = str(d.get("billDueDate") or "")
    due = f"{due[:4]}-{due[4:6]}-{due[6:]}" if len(due) == 8 and due.isdigit() else due
    return {"customer_name": d.get("utilitycustomername"), "amount_inr": int(round(float(d["amount"]))), "due_date": due,
            "bill_ref": d.get("bbpstrxnrefid") or ref, "provider": label, "sandbox": True}

def parse_pay(r, ref, label):
    d = r.get("data") or {}
    if r.get("status") != 0 or str(d.get("tx_status")) != "0": raise RuntimeError(f"eko_pay_failed:{r.get('status')}:{d.get('txstatus_desc', '')}"[:120])
    return {"reference": d.get("tid") or ref, "client_ref_id": ref, "status": d.get("status_text", "SUCCESS"), "provider": label}

# ---------------- Razorpay ----------------
def sim_dir():
    d = Path(env("SIM_RAZORPAY_DIR") or HERE / ".sim_razorpay"); d.mkdir(exist_ok=True); return d
def sim_mark_paid(link_id): (sim_dir() / f"{link_id}.paid").write_text("1")

class Razorpay:
    """Real path: basic auth key_id:key_secret, POST /v1/payment_links, GET /v1/payment_links/{id}. No keys -> SIMULATED_RAZORPAY."""
    def __init__(self):
        self.live = bool(env("RAZORPAY_KEY_ID") and env("RAZORPAY_KEY_SECRET")); self.label = "RAZORPAY_TEST" if self.live else "SIMULATED_RAZORPAY"
        self.auth = (env("RAZORPAY_KEY_ID"), env("RAZORPAY_KEY_SECRET"))
    def create_link(self, amount_inr, reference_id, description, contact=None):
        if not self.live:
            lid = "plink_SIM" + uuid.uuid4().hex[:12]; return {"id": lid, "short_url": f"https://rzp.io/simulated/{lid}", "status": "created"}
        body = {"amount": int(amount_inr) * 100, "currency": "INR", "accept_partial": False, "reference_id": reference_id[:40],
                "description": description[:2000], "upi_link": env("RAZORPAY_UPI_LINK").lower() != "false", "notify": {"sms": False, "email": False}}
        if contact: body["customer"] = {"contact": contact}
        r = requests.post(RZP + "/v1/payment_links", auth=self.auth, json=body, timeout=30)
        if r.status_code >= 400: raise RuntimeError(f"razorpay_create_failed:{r.status_code}")
        j = r.json(); return {"id": j["id"], "short_url": j["short_url"], "status": j.get("status", "created")}
    def status(self, link_id):
        if not self.live: return "paid" if (sim_dir() / f"{link_id}.paid").exists() else "created"
        r = requests.get(f"{RZP}/v1/payment_links/{link_id}", auth=self.auth, timeout=30)
        if r.status_code >= 400: raise RuntimeError(f"razorpay_status_failed:{r.status_code}")
        return r.json().get("status")

def stop_eko_mock(p):
    import signal
    if p:
        try: os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError: pass


# ---------------- UPI QR demo (contract v1.5) ----------------
def select_provider():
    """Razorpay keys -> 'razorpay'; else UPI_DEMO_VPA -> 'upi_qr_demo'; else 'simulated'."""
    if env("RAZORPAY_KEY_ID") and env("RAZORPAY_KEY_SECRET"): return "razorpay"
    return "upi_qr_demo" if env("UPI_DEMO_VPA") else "simulated"

def upi_uri(vpa, name, amount_inr, case_number, payment_id):
    """Amount is always whole rupees from the fetched bill, rendered exactly as '<n>.00'. Params percent-encoded (spaces as %20)."""
    amt = int(amount_inr)
    q = [("pa", vpa), ("pn", name or "Akshaya Demo"), ("am", f"{amt}.00"), ("cu", "INR"), ("tn", f"Akshaya demo case {case_number}"), ("tr", payment_id)]
    return "upi://pay?" + "&".join(f"{k}={quote(str(v), safe='@.-_')}" for k, v in q)
