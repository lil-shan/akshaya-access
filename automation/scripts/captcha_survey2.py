"""Read-only survey v2: landing page -> click ONE visible navigation link (login/citizen/apply) -> probe captcha + login method.
Never types into fields, never presses OTP/submit buttons. Navigation targets are matched on link text only."""
import json, re, sys
from playwright.sync_api import sync_playwright
PORTALS = {
 "edistrict-kerala": "https://edistrict.kerala.gov.in/",
 "ksmart": "https://ksmart.lsgkerala.gov.in/ui/web-portal",
 "kseb-quickpay": "https://wss.kseb.in/selfservices/quickpay",
 "kwa-epay": "https://epay.kwa.kerala.gov.in/",
 "civil-supplies-ecitizen": "https://ecitizen.civilsupplieskerala.gov.in/",
 "voters-eci": "https://voters.eci.gov.in/login",
 "pan-protean": "https://www.protean-tinpan.com/",
 "pan-incometax-epan": "https://www.incometax.gov.in/iec/foportal/",
 "passport-seva": "https://services1.passportindia.gov.in/forms/",
 "epfo-member": "https://unifiedportal-mem.epfindia.gov.in/",
 "kerala-police-thuna": "https://thuna.keralapolice.gov.in/",
}
NAV = re.compile(r"^\s*(citizen\s*login|user\s*login|login|log\s*in|sign\s*in|apply\s*online|new\s*(user|application)|instant\s*e-?pan|get\s*new\s*e-?pan|applicant\s*login|member\s*login|register)\b", re.I)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BAD_BTN = re.compile(r"otp|submit|verify|send|proceed", re.I)
def probe(pg):
    h = pg.content().lower(); t = pg.inner_text("body").lower() if pg.query_selector("body") else ""
    cap = []
    if re.search(r"recaptcha|g-recaptcha", h): cap.append("reCAPTCHA")
    if "hcaptcha" in h: cap.append("hCaptcha")
    if "captcha" in h and not cap: cap.append("image")
    if cap and re.search(r"audio|listen|speak|volume", h): cap.append("audio option present")
    if "captcha" not in h and not cap: cap = ["none"]
    login = [n for n, p in [("mobile OTP", r"mobile.{0,30}otp|otp.{0,30}mobile|send otp|generate otp|get otp|otp"), ("Aadhaar", r"aadhaar|aadhar"),
                            ("username/password", r"password|user\s*id|username")] if re.search(p, t)]
    return cap, login or ["none seen"]
rows = []
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    for name, url in PORTALS.items():
        ctx = b.new_context(viewport={"width": 1366, "height": 900}, ignore_https_errors=True, user_agent=UA, locale="en-IN")
        pg = ctx.new_page(); r = {"portal": name, "url": url, "clicked": None}
        try:
            resp = None
            for t in (60000, 90000):
                try: resp = pg.goto(url, timeout=t, wait_until="domcontentloaded"); break
                except Exception as e: err = e
            if resp is None: raise err
            pg.wait_for_timeout(4000); r["status"] = resp.status
            r["landing"] = probe(pg)
            for el in pg.query_selector_all("a:visible, button:visible"):
                txt = (el.inner_text() or "").strip()
                if txt and len(txt) < 40 and NAV.search(txt) and not BAD_BTN.search(txt):
                    r["clicked"] = txt
                    try: el.click(timeout=8000); pg.wait_for_timeout(5000)
                    except Exception as e: r["click_error"] = str(e).split("\n")[0][:60]
                    break
            r["final_url"] = pg.url; r["captcha"], r["login"] = probe(pg)
            pg.screenshot(path=f"reports/captcha/{name}-login.png")
        except Exception as e: r["error"] = str(e).split("\n")[0][:90]
        rows.append(r); print(json.dumps(r), file=sys.stderr); ctx.close()
    b.close()
json.dump(rows, open("reports/captcha-survey2.json", "w"), indent=1)
