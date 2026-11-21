"""Read-only survey of public login/start pages. Never clicks, types or submits."""
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
 "pan-incometax-epan": "https://eportal.incometax.gov.in/iec/foservices/#/pre-login/instant-e-pan",
 "passport-seva": "https://services1.passportindia.gov.in/forms/",
 "epfo-member": "https://unifiedportal-mem.epfindia.gov.in/memberinterface/",
 "kerala-police-thuna": "https://thuna.keralapolice.gov.in/",
}
def probe(page):
    h = page.content().lower()
    t = page.inner_text("body").lower() if page.query_selector("body") else ""
    cap = []
    if "recaptcha" in h or "g-recaptcha" in h: cap.append("reCAPTCHA")
    if "hcaptcha" in h: cap.append("hCaptcha")
    if re.search(r"captcha", h) and not cap:
        cap.append("image (captcha text/element in DOM)")
    if re.search(r"audio.{0,40}captcha|captcha.{0,40}audio|listen", h): cap.append("audio option?")
    login = [n for n, p in [("mobile OTP", r"mobile.{0,30}otp|otp.{0,30}mobile|send otp|generate otp|get otp"),
              ("Aadhaar OTP", r"aadhaar.{0,40}otp|otp.{0,40}aadhaar|aadhaar"),
              ("password", r"password")] if re.search(p, t)]
    return cap or ["none visible"], login or ["none visible"]
rows = []
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for name, url in PORTALS.items():
        ctx = b.new_context(viewport={"width": 1280, "height": 900}, ignore_https_errors=True)
        pg = ctx.new_page(); r = {"portal": name, "url": url}
        try:
            resp = pg.goto(url, timeout=45000, wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
            r["reachable"] = f"yes (HTTP {resp.status if resp else '?'})"
            r["captcha"], r["login"] = probe(pg)
            pg.screenshot(path=f"reports/captcha/{name}.png")
        except Exception as e:
            r["reachable"] = "no: " + str(e).split("\n")[0][:80]; r["captcha"] = r["login"] = ["n/a"]
        rows.append(r); print(r, file=sys.stderr); ctx.close()
    b.close()
json.dump(rows, open("reports/captcha-survey.json", "w"), indent=1)
