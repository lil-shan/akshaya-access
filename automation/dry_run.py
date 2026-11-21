"""Real-portal DRY RUN engine (contract v1.2). Fills pages up to the last preview, never submits.
Safety layers: (1) per-page click allowlist, (2) global denylist regex on the element's own text/id/name/value/aria-label/title,
(3) unknown page -> abort with screenshot, (4) Aadhaar prompt -> stop (citizen enters it on the portal).
Runtime-only values (mobile, password, OTP, captcha) go through worker.ask (used once, nulled) and are never logged/stored."""
import re, json
from pathlib import Path
HERE = Path(__file__).parent
DENY = re.compile(r"submit|confirm|e-?sign|final|pay|register|declare", re.I)
AADHAAR_SEL = "input[name*=aadhaar i], input[id*=aadhaar i], input[placeholder*=aadhaar i]"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"  # ECI's WAF blocks default headless UA
MAX_PAGES, MAX_VISITS = 30, 6

class GuardError(Exception): pass          # a click was refused by the allowlist/denylist
class AbortRun(Exception): pass            # unknown page / stuck: abort safely (screenshot taken by caller)

def check_click(selector, descriptor, allow):
    """Pure guard. descriptor = the element's own text/id/name/value/aria-label/title joined. Raises GuardError."""
    if selector not in allow: raise GuardError(f"click_not_allowlisted:{selector}")
    if DENY.search(selector) or DENY.search(descriptor or ""): raise GuardError(f"click_denied_by_denylist:{(descriptor or selector)[:60]}")

def describe(page, selector):
    return page.eval_on_selector(selector, """e=>[e.innerText,e.value,e.id,e.getAttribute('name'),e.getAttribute('aria-label'),e.title,e.getAttribute('alt')].filter(Boolean).join(' ')""")

def guarded_click(page, selector, allow):
    check_click(selector, describe(page, selector), allow)
    page.click(selector)

# [seen] = observed read-only on the real portal / in its public bundle; [assumed] = not visible without logging in.
PORTALS = {
 "voter_form6": dict(  # flow.md: portals/voter_form6/flow.md
    url="https://voters.eci.gov.in/login", ua=UA, logout=["text=Logout", "text=Log out"],
    pages=[
     dict(id="login", detect="#mobOrEpic", steps=[("mobile", "#mobOrEpic"),   # [seen]
          ("captcha", dict(input="#captcha", image="img[alt=Captcha]", audio="img[alt='Read aloud captcha']")),  # [seen]
          ("click", "button.library-btn")]),                                  # [seen] "Request OTP"
     dict(id="otp", detect="input[name=otp]", steps=[("otp", "input[name=otp]"), ("click", "#verify-otp")]),  # [assumed]
     dict(id="dashboard", detect="#form6-card", steps=[("click", "#form6-card")]),  # [assumed] card "New registration for general electors (Form 6)"
     dict(id="form6", detect="#form6-section", steps=[("fill", None), ("next", "#save-next")]),  # [assumed] sections A-L, Save & Next
     dict(id="preview", detect="#preview", terminal=True),                       # [assumed] last page before declaration/submit
    ]),
 "thuna_lost_property": dict(
    url="https://thuna.keralapolice.gov.in/", ua=None, logout=["#logout"],
    pages=[
     dict(id="home", detect="button.signInbutton:visible", steps=[("click", "button.signInbutton:visible")]),  # [seen] opens login panel
     dict(id="login", detect="input[name=userName]", steps=[("mobile", "input[name=userName]"), ("password", "input[name=password]"),   # [seen in bundle]
          ("captcha", dict(input="input[name=captcha]", image="img[alt=captcha], .captcha img", audio=None)),  # [seen] image only, "Reload image"
          ("click", "#login-btn")]),                                              # [assumed]
     dict(id="otp", detect="input[name=otp]", steps=[("otp", "input[name=otp]"), ("click", "#verify-otp")]),  # [seen in bundle: 6-digit otp]
     dict(id="dashboard", detect="#lost-property-link", steps=[("click", "#lost-property-link")]),            # [assumed]
     dict(id="lost_new", detect="#new-lost-request", steps=[("click", "#new-lost-request")]),                 # [assumed]
     dict(id="lost_form", detect="#lost-form", steps=[("fill", None), ("next", "#preview-btn")]),             # [assumed] next = "Preview & Submit" -> denylisted -> stop
    ]),
}

def load_fields(service): return json.loads((HERE / "portals" / service / "fields.json").read_text())

def run_dry(page, db, job, case, service, shot, ask, base_url=None, log=None):
    """Drive `page` through the portal spec. Returns result dict. `ask` = worker.ask. Raises AbortRun on unknown page."""
    spec = PORTALS[service]; cid = case["id"]; data = case.get("data") or {}; keys = [f["key"] for f in load_fields(service)]
    ev = lambda m, d=None: db.event(cid, "step", m, d)
    page.goto(base_url or spec["url"]); page.wait_for_load_state(); visits = {}; stopped = None
    try:
        for _ in range(MAX_PAGES):
            if page.query_selector(AADHAAR_SEL):
                shot(page, "aadhaar-stop"); ev("Portal asks for Aadhaar: the citizen enters it on the portal. Dry run stops here.")
                stopped = "aadhaar_citizen_enters_on_portal"; break
            pg = next((p for p in spec["pages"] if page.query_selector(p["detect"])), None)
            if pg is None:
                shot(page, "unknown-page"); raise AbortRun("unknown_page")
            visits[pg["id"]] = visits.get(pg["id"], 0) + 1
            if visits[pg["id"]] > MAX_VISITS: shot(page, "stuck"); raise AbortRun(f"stuck_on:{pg['id']}")
            ev(f"On page: {pg['id']}")
            if pg.get("terminal"):
                shot(page, f"{pg['id']}-preview"); stopped = "reached_preview"; break
            allow = {s[1] for s in pg.get("steps", []) if s[0] in ("click", "next")}
            nxt = None
            for kind, arg in pg.get("steps", []):
                if kind == "mobile":
                    _, v = ask(db, job, [("field", "Mobile number registered for this login", None)]); page.fill(arg, v); v = None
                elif kind == "password":
                    _, v = ask(db, job, [("field", "Password for this portal login (used once, not stored)", None)]); page.fill(arg, v); v = None
                elif kind == "otp":
                    _, v = ask(db, job, [("otp", "The portal sent an OTP by SMS to your phone. Please read it out.", None)]); page.fill(arg, v); v = None
                elif kind == "captcha":
                    media = [("captcha_image", "Read the characters shown in the captcha image.", None)]; base = f"{cid}/{job['id']}"
                    if arg.get("audio") and page.query_selector(arg["audio"]):  # audio preferred; requested once per run
                        try:
                            with page.expect_response(lambda r: "oice" in r.url or "audio" in r.url, timeout=8000) as ri: page.click(arg["audio"])
                            db.upload(f"{base}/captcha.audio", ri.value.body(), ri.value.headers.get("content-type", "audio/mpeg"))
                            media.insert(0, ("captcha_audio", "Listen to the audio captcha and say the characters you hear.", f"{base}/captcha.audio"))
                        except Exception: ev("Audio captcha unavailable; using image only")
                    img = page.query_selector(arg["image"])
                    if img: db.upload(f"{base}/captcha.png", img.screenshot(), "image/png"); media[-1] = (media[-1][0], media[-1][1], f"{base}/captcha.png")
                    _, v = ask(db, job, media); page.fill(arg["input"], v); v = None
                elif kind == "fill":
                    filled = []
                    for k in keys:
                        val = data.get(k); el = page.query_selector(f"[name={k}]")
                        if val in (None, "") or not el: continue
                        (page.select_option if el.evaluate("e=>e.tagName") == "SELECT" else page.fill)(f"[name={k}]", str(val)); filled.append(k)
                    ev(f"Filled {len(filled)} fields", {"fields": filled}); shot(page, f"{pg['id']}-filled")
                elif kind == "click":
                    guarded_click(page, arg, allow); page.wait_for_load_state()
                elif kind == "next": nxt = arg
            if nxt:
                try: guarded_click(page, nxt, allow); page.wait_for_load_state()
                except GuardError as e:
                    shot(page, f"{pg['id']}-stop"); ev(f"Next control refused by guard ({e}); stopping before final step")
                    stopped = "guard_refused_next"; break
        else: raise AbortRun("too_many_pages")
    finally:
        for sel in spec["logout"]:  # best effort log out; logout controls are the only extra clicks allowed
            try:
                if page.query_selector(sel): guarded_click(page, sel, set(spec["logout"])); ev("Logged out"); break
            except Exception: pass
    return {"stopped_before_submit": True, "stopped_reason": stopped, "service": service}
