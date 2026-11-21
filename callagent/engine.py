"""Deterministic call flow (no LLM). IO protocol: io.say(text), io.hear(label=None) -> str (raises Hangup), io.play(wav).
Events (actor 'voice') carry normalized meanings only. Spoken OTPs/passwords/captchas are never written anywhere
except the job_prompts answer, and a scrubber blocks any known secret from reaching events."""
import re
import time

import parsing as P

CATEGORIES = {  # id -> (Malayalam, English)
    "certificates": ("സർട്ടിഫിക്കറ്റുകൾ", "certificates"), "insurance": ("ഇൻഷുറൻസ്", "insurance"),
    "bills": ("ബില്ലുകൾ", "bills"), "elections": ("തിരഞ്ഞെടുപ്പ്", "elections voter"),
    "identity": ("തിരിച്ചറിയൽ രേഖകൾ", "identity documents"), "police": ("പോലീസ്", "police"),
    "agriculture": ("കൃഷി", "agriculture"), "employment": ("തൊഴിൽ", "employment")}
_FALLBACK_CAT = {"edistrict": "certificates", "ksmart": "certificates", "ration": "identity", "pmjjby": "insurance",
                 "pmsby": "insurance", "pmfby": "agriculture", "kseb": "bills", "kwa": "bills", "voter": "elections",
                 "thuna": "police", "pan": "identity", "passport": "identity", "epf": "employment"}

T = dict(
    greeting="നമസ്കാരം. ഇത് അക്ഷയ ആക്സസ് ആണ്. ഞാൻ ഒരു AI സഹായിയാണ്, മനുഷ്യനല്ല. ഞാൻ ഒരിക്കലും നിങ്ങളുടെ UPI പിൻ ചോദിക്കില്ല. "
             "സർക്കാർ പോർട്ടൽ നിങ്ങൾക്ക് OTP അല്ലെങ്കിൽ പാസ്‌വേഡ് ആവശ്യപ്പെട്ടാൽ മാത്രമേ ഞാൻ അത് ചോദിക്കൂ.",
    cat_q="ഏത് തരം സേവനമാണ് വേണ്ടത്? ", svc_q="ഏത് സേവനമാണ് വേണ്ടത്? ", retry="ക്ഷമിക്കണം, മനസ്സിലായില്ല. ഒന്നുകൂടി പറയാമോ?",
    name_q="നിങ്ങളുടെ മുഴുവൻ പേര് പറയാമോ?", known="നിങ്ങൾ {name} ആണോ? അതെ അല്ലെങ്കിൽ അല്ല എന്ന് പറയൂ.",
    heard="ഞാൻ കേട്ടത്: {x}. ശരിയാണോ? അതെ അല്ലെങ്കിൽ അല്ല എന്ന് പറയൂ.", yn="അതെ അല്ലെങ്കിൽ അല്ല എന്ന് പറയൂ.",
    optional="ഇല്ലെങ്കിൽ 'ഇല്ല' എന്ന് പറയൂ.", summary="വിവരങ്ങൾ ഒന്നുകൂടി വായിക്കാം. ",
    consent="ഈ വിവരങ്ങൾ ഉപയോഗിച്ച് ഞാൻ നിങ്ങൾക്കു വേണ്ടി ഫോം പൂരിപ്പിക്കട്ടെ? ഒന്നും അവസാനമായി സമർപ്പിക്കില്ല. "
            "അനുമതി തരുന്നുവെങ്കിൽ 'അതെ' എന്ന് മാത്രം പറയൂ.",
    dry="ഇത് യഥാർത്ഥ പോർട്ടൽ തുറക്കും, നിങ്ങളുടെ ഫോണിലേക്ക് യഥാർത്ഥ OTP വരും. ഒന്നും സമർപ്പിക്കില്ല. ",
    declined="ശരി, അനുമതിയില്ലാതെ ഞാൻ ഒന്നും ചെയ്യില്ല. വിവരങ്ങൾ കേസിൽ ഡ്രാഫ്റ്റ് ആയി സൂക്ഷിച്ചിട്ടുണ്ട്. നന്ദി.",
    working="ഞാൻ ഇപ്പോൾ തുടങ്ങുകയാണ്. ദയവായി ലൈനിൽ തുടരൂ.",
    otp="പോർട്ടൽ നിങ്ങളുടെ ഫോണിലേക്ക് ഒരു OTP അയച്ചു. അത് പതുക്കെ പറയാമോ?",
    field="പോർട്ടലിന് ഒരു വിവരം ആവശ്യമുണ്ട്: {t}. പറയാമോ?",
    password="പോർട്ടൽ നിങ്ങളുടെ പാസ്‌വേഡ് ആവശ്യപ്പെടുന്നു. അത് ഒരു തവണ മാത്രം ഉപയോഗിച്ച് മായ്ക്കും. നിങ്ങളുടെ സ്വന്തം അക്കൗണ്ട് ആണെങ്കിൽ മാത്രം പറയൂ.",
    captcha="പോർട്ടൽ ഒരു ഓഡിയോ ക്യാപ്ച പ്ലേ ചെയ്യും. ശ്രദ്ധിച്ച് കേട്ട് അക്കങ്ങൾ ആവർത്തിക്കൂ. വീണ്ടും കേൾക്കാൻ 'വീണ്ടും' എന്ന് പറയൂ.",
    captcha_img="ഈ ക്യാപ്ച ചിത്രമായി മാത്രമേ ലഭ്യമുള്ളൂ. ഫോണിലൂടെ ഇത് ഇപ്പോൾ സാധ്യമല്ല, വാട്സ്ആപ്പ് ആവശ്യമാണ്. "
                "ഇത് കേസിൽ രേഖപ്പെടുത്തിയിട്ടുണ്ട്. ഞാൻ ഒന്നും ഉറപ്പ് നൽകുന്നില്ല.",
    handoff="ഈ ആവശ്യം ഞാൻ കേസിൽ രേഖപ്പെടുത്തി. ഫോണിൽ ഇത് ചെയ്യാൻ എനിക്ക് ഇപ്പോൾ കഴിയില്ല. ഒരാൾ വിളിക്കുമെന്നോ ഇത് നടക്കുമെന്നോ ഞാൻ ഉറപ്പ് നൽകുന്നില്ല. "
            "ദയവായി അടുത്തുള്ള അക്ഷയ കേന്ദ്രത്തെ സമീപിക്കുക.",
    bye="നന്ദി. നമസ്കാരം.",
    pay_wait="പേയ്മെന്റ് അഭ്യർത്ഥന തയ്യാറായി. നിങ്ങളുടെ സ്വന്തം UPI ആപ്പിൽ നിങ്ങൾ തന്നെ പിൻ നൽകണം, ഞാൻ ഒരിക്കലും പിൻ ചോദിക്കില്ല. ഞാൻ കാത്തിരിക്കാം.",
)
DONE = ("succeeded", "failed", "cancelled")


class Hangup(Exception):
    pass


class Handoff(Exception):
    def __init__(self, reason, text=None):
        super().__init__(reason)
        self.reason, self.text = reason, text or T["handoff"]


def _tokset(s):
    return {t[:5] for t in P.tokens(s) if len(t) >= 3 and not t.isdigit()}


def pick(text, options):
    """options: [(key, [aliases])]. By number ('2'), else unique best token overlap. None if unclear."""
    d = P.parse_digits(text)
    if d and len(d) == 1 and 1 <= int(d) <= len(options) and len(P.tokens(text)) <= 3:
        return options[int(d) - 1][0]
    said = _tokset(text)
    scores = [(len(said & set().union(*(_tokset(a) for a in al))), k) for k, al in options]
    best = max(scores)[0] if scores else 0
    winners = [k for s, k in scores if s == best]
    return winners[0] if best and len(winners) == 1 else None


def lookup(obj, path):
    for part in path.split("."):
        obj = obj.get(part) if isinstance(obj, dict) else None
    return obj


class Call:
    def __init__(self, io, db, phone=None, extra_data=None, poll=1.0, job_wait=900):
        self.io, self.db, self.phone = io, db, phone
        self.extra, self.poll, self.job_wait = extra_data or {}, poll, job_wait
        self.case = self.citizen = self.svc = None
        self.data, self.pending, self.secrets = {}, [], set()

    # ---- plumbing -------------------------------------------------------------------------
    def scrub(self, s):
        for sec in self.secrets:
            s = s.replace(sec, "[redacted]")
        return s

    def ev(self, type, msg, data=None):
        row = (type, self.scrub(msg), data or {})
        if self.case:
            self.db.event(self.case["id"], *row)
        else:
            self.pending.append(row)

    def say(self, text, m):
        self.io.say(self.scrub(text))
        self.ev("agent_turn", m)

    def hear(self, m=None, secret=None, person=True):
        """secret = transcript label like '[OTP given]'. Person requests are honoured except on secret turns."""
        text = self.io.hear(secret)
        if secret is None and person and P.wants_person(text):
            raise Handoff("asked_for_person")
        if m:
            self.ev("citizen_turn", m)
        return text

    def yes(self, question, m, tries=3):
        """Strict whole-word yes. True / False; unclear twice -> False."""
        for _ in range(tries):
            self.say(question, m)
            ans = P.parse_yes_no(self.hear())
            if ans is not None:
                self.ev("citizen_turn", "confirmed" if ans else "declined")
                return ans
            question = T["yn"]
        self.ev("citizen_turn", "unclear")
        return False

    # ---- flow -----------------------------------------------------------------------------
    def run(self):
        try:
            self.say(T["greeting"], "greeting: AI assistant, never asks UPI PIN, OTP/password only when portal sends")
            self.choose_service()
            self.identify()
            self.open_case()
            self.collect()
            if self.consent():
                self.execute()
        except Hangup:
            self.ev("call_ended", "Caller hung up")
        except Handoff as h:
            self.ev("handoff", f"Handoff: {h.reason}; nothing promised")
            self.io.say(h.text)
        self.ev("call_ended", "Call finished")
        return self.case

    def choose_service(self):
        svcs = self.db.services()
        for s in svcs:
            s["_cat"] = s.get("category") or _FALLBACK_CAT.get(s["id"].split("_")[0], "certificates")
        cats = [c for c in CATEGORIES if any(s["_cat"] == c for s in svcs)]
        opts = [(c, [CATEGORIES[c][0], CATEGORIES[c][1]]) for c in cats]
        cat = self.choose(T["cat_q"], [(c, CATEGORIES[c][0]) for c in cats], opts, "ask: service category")
        mine = [s for s in svcs if s["_cat"] == cat]
        key = self.choose(T["svc_q"], [(s["id"], s.get("name_ml") or s["name"]) for s in mine],
                          [(s["id"], [s["name"], s.get("name_ml") or "", s["id"].replace("_", " ")]) for s in mine],
                          "ask: service")
        self.svc = next(s for s in mine if s["id"] == key)

    def choose(self, q, shown, opts, m):
        listing = ". ".join(f"{i}. {name}" for i, (_, name) in enumerate(shown, 1))
        for _ in range(3):
            self.say(q + listing, m)
            key = pick(self.hear(), opts)
            if key:
                self.ev("citizen_turn", f"chose {key}")
                return key
            self.say(T["retry"], "retry")
        raise Handoff("unsupported_or_unclear_service")

    def identify(self):
        masked = f"******{self.phone[-4:]}" if self.phone else None
        found = self.db.find_citizens(masked) if masked else []
        if len(found) == 1 and self.yes(T["known"].format(name=found[0]["full_name"]), "ask: confirm known citizen"):
            self.citizen = found[0]
            return
        name = self.ask_value({"key": "full_name", "type": "text", "required": True, "ask_ml": T["name_q"]})
        self.citizen = self.db.add_citizen({"full_name": name, "phone_masked": masked})

    def open_case(self):
        for f in self.svc["fields"]:
            if f["key"] == "confirm_amount" and self.svc["submission"] == "api":
                continue
            src = f.get("source") or ""
            val = lookup({"citizen": self.citizen}, src) if src.startswith("citizen.") else None
            if val not in (None, ""):
                self.data[f["key"]] = str(val)
        self.case = self.db.add_case({"citizen_id": self.citizen["id"], "service_id": self.svc["id"], "status": "draft",
                                      "channel": "phone", "data": dict(self.data, **self.extra)})
        for t, m, d in self.pending:
            self.db.event(self.case["id"], t, m, d)
        self.pending = []
        self.ev("call_started", "Inbound phone call; caller identified", {"service": self.svc["id"], "prefilled": sorted(self.data)})

    # ---- fields ---------------------------------------------------------------------------
    def parse(self, f, raw):
        t, val = f["type"], None
        if t in ("text", "textarea", "email"):
            val = raw.strip()[:200] if len(raw.strip()) >= 2 else None
        elif t == "number":
            val = P.parse_digits(raw) or None
        elif t == "phone":
            val = P.parse_phone(raw)
        elif t == "account_number":
            d = P.parse_digits(raw)
            val = d if 9 <= len(d) <= 18 else None
        elif t == "ifsc":
            val = P.parse_ifsc(raw)
        elif t == "date":
            val = P.parse_date(raw)
        elif t == "yesno":
            a = P.parse_yes_no(raw)
            val = None if a is None else ("yes" if a else "no")
        elif t == "select":
            opts = f.get("options") or []
            val = pick(raw, [(o, [o]) for o in opts])
        if val is not None and f.get("pattern") and not re.fullmatch(f["pattern"], val):
            val = None
        return val

    @staticmethod
    def readback(f, val):
        t = f["type"]
        if t in ("number", "phone", "account_number"):
            return P.digits_ml(val)
        if t == "date":
            return P.digits_ml(val[8:10] + val[5:7] + val[:4])
        if t == "ifsc":
            return P.spell(val)
        return val

    def ask_value(self, f):
        """Ask one field until a confirmed valid value. None = optional skipped. Handoff if a required field fails."""
        label = f["key"]
        for _ in range(4):
            q = f.get("ask_ml") or f"{f.get('label_ml') or f.get('label') or label} പറയാമോ?"
            if f["type"] == "select":
                q += " " + ". ".join(f"{i}. {o}" for i, o in enumerate(f.get("options") or [], 1))
            if not f.get("required"):
                q += " " + T["optional"]
            self.say(q, f"ask: {label}")
            raw = self.hear(person=f["type"] not in ("text", "textarea", "email"))
            if not f.get("required") and f["type"] not in ("yesno", "select") and P.parse_yes_no(raw) is False:
                self.ev("citizen_turn", f"skipped optional {label}")
                return None
            val = self.parse(f, raw)
            if val is None:
                self.ev("citizen_turn", f"invalid {label}")
                self.say(T["retry"], "retry")
                continue
            self.ev("citizen_turn", f"gave {label} ({f['type']})")
            if f["type"] in ("yesno", "select") or self.yes(T["heard"].format(x=self.readback(f, val)), f"confirm: {label}"):
                return val
        if f.get("required"):
            raise Handoff(f"could_not_collect:{label}")
        return None

    def collect(self):
        for f in self.svc["fields"]:
            if f["key"] in self.data or (f["key"] == "confirm_amount" and self.svc["submission"] == "api"):
                continue
            val = self.ask_value(f)
            if val is not None:
                self.data[f["key"]] = val
                self.db.set_case(self.case["id"], data=dict(self.data, **self.extra))

    def summary_lines(self):
        out = []
        for f in self.svc["fields"]:
            if f["key"] in self.data:
                out.append(f"{f.get('label_ml') or f.get('label') or f['key']}: {self.readback(f, self.data[f['key']])}")
        return out

    def consent(self):
        sub = self.svc["submission"]
        self.say(T["summary"] + ". ".join(self.summary_lines()), "summary read")
        q = (T["dry"] if sub == "portal_dry_run" else "") + T["consent"]
        if not self.yes(q, "ask: consent to run"):
            self.ev("consent_declined", "Caller did not consent; case stays draft")
            self.io.say(T["declined"])
            return False
        name = self.svc["name"]
        self.db.add_consent(self.case["id"], "automation_run",
                            f"Citizen consented by voice (phone) to the AI assistant filling the {name} application with the details read back. Nothing is finally submitted.")
        if sub == "portal_dry_run":
            self.db.add_consent(self.case["id"], "portal_dry_run",
                                "Citizen consented by voice to a dry run on the REAL portal: a real OTP will be sent; nothing will be submitted.")
        self.ev("consent_given", "Consent recorded by voice (channel phone)", {"kind": "automation_run"})
        return True

    # ---- jobs -----------------------------------------------------------------------------
    def queue(self, kind, mode):
        self.db.set_case(self.case["id"], status="ready")
        job = self.db.add_job(self.case["id"], kind, mode)
        self.ev("job_queued", f"Job {kind} ({mode}) queued", {"job_id": job["id"]})
        return job

    def execute(self):
        sub = self.svc["submission"]
        kind, mode = {"pdf": ("fill_pdf", "mock"), "mock_portal": ("portal_fill", "mock"),
                      "portal_dry_run": ("portal_fill", "dry_run"), "api": ("bbps_fetch", "mock")}[sub]
        self.say(T["working"], "working")
        job = self.run_job(self.queue(kind, mode))
        if sub == "api":
            if job["status"] == "succeeded" and self.pay(job):
                job = self.run_job(self.queue("payment_collect", "mock"))
            elif job["status"] == "succeeded":
                return self.finish("ശരി, പണമടച്ചിട്ടില്ല.", "payment declined")
        self.report(job)

    def pay(self, fetch_job):
        r = fetch_job.get("result") or {}
        amt = r.get("amount_inr")
        if amt is None:
            return False
        amt = int(amt) if float(amt) == int(float(amt)) else amt
        self.say(f"ബിൽ കിട്ടി. പേര്: {r.get('customer_name', '')}. തുക {amt} രൂപ, അതായത് {P.digits_ml(str(amt)) if str(amt).isdigit() else amt}. "
                 f"അവസാന തീയതി {r.get('due_date', '')}. ഈ തുക അടയ്ക്കട്ടെ? നിങ്ങളുടെ UPI ആപ്പിൽ നിങ്ങൾ തന്നെ പിൻ നൽകണം, ഞാൻ ഒരിക്കലും പിൻ ചോദിക്കില്ല. "
                 "സമ്മതമെങ്കിൽ 'അതെ' എന്ന് മാത്രം പറയൂ.", "payment amount read back")
        if P.parse_yes_no(self.hear()) is not True:
            self.ev("citizen_turn", "payment not confirmed")
            return False
        self.ev("citizen_turn", "confirmed payment amount")
        self.db.add_consent(self.case["id"], "payment",
                            f"Citizen confirmed by voice (phone) payment of ₹{amt} for this bill; the citizen pays in their own UPI app.")
        data = dict(self.db.get_case(self.case["id"]).get("data") or {}, confirm_amount="yes")
        self.db.set_case(self.case["id"], data=data)
        self.ev("consent_given", "Payment consent recorded by voice", {"kind": "payment", "amount_inr": amt})
        return True

    def run_job(self, job):
        handled, announced, end = set(), False, time.time() + self.job_wait
        while True:
            cur = self.db.get_job(job["id"])
            prompts = sorted(self.db.open_prompts(job["id"]), key=lambda p: p["kind"] != "captcha_audio")
            for p in prompts:
                if p["id"] in handled:
                    continue
                handled.add(p["id"])
                if p["kind"] == "captcha_image" and any(q["kind"] == "captcha_audio" for q in prompts):
                    continue
                self.relay(p)
            res = cur.get("result") or {}
            if not announced and (res.get("upi_uri") or res.get("short_url")) and cur["status"] not in DONE:
                announced = True
                self.say(T["pay_wait"], "payment pending, caller pays in own UPI app")
            if cur["status"] in DONE:
                return cur
            if time.time() > end:
                return cur
            if not prompts:
                time.sleep(self.poll)

    def relay(self, p):
        kind = p["kind"]
        if kind == "otp":
            self.relay_secret(p, T["otp"], "[OTP given]", lambda r: (lambda d: d if 4 <= len(d) <= 8 else None)(P.parse_digits(r)))
        elif kind == "password":
            self.relay_secret(p, T["password"], "[password given]", lambda r: r.strip() or None)
        elif kind == "field":
            numeric = bool(re.search(r"mobile|phone|number", (p.get("prompt_text") or "").lower()))
            self.relay_secret(p, p.get("prompt_text_ml") or T["field"].format(t=p.get("prompt_text") or ""),
                              "[field value given]", (lambda r: P.parse_phone(r)) if numeric else (lambda r: r.strip() or None))
        elif kind == "captcha_audio":
            self.relay_captcha(p)
        elif kind == "captcha_image":
            self.ev("captcha_image_unsupported", "Image-only captcha: WhatsApp needed, not supported by voice yet")
            raise Handoff("captcha_image_needs_whatsapp", T["captcha_img"])
        elif kind == "confirm":
            self.say(p.get("prompt_text_ml") or p.get("prompt_text") or "", "relay: confirm prompt")
            ans = P.parse_yes_no(self.hear())
            if ans is not None:
                self.db.answer_prompt(p["id"], "yes" if ans else "no")
                self.ev("citizen_turn", "confirm answered " + ("yes" if ans else "no"))

    def relay_secret(self, p, question, label, parse):
        for _ in range(3):
            self.say(p.get("prompt_text_ml") or question if p["kind"] == "field" else question, f"relay: {p['kind']} requested")
            val = parse(self.hear(secret=label))
            if val:
                self.secrets.add(val)
                self.db.answer_prompt(p["id"], val)
                self.ev("citizen_turn", label)
                return
            self.say(T["retry"], "retry")
        self.ev("citizen_turn", f"{p['kind']} not understood; prompt left to expire")

    def relay_captcha(self, p):
        wav = self.db.download(p["media_path"])
        self.say(T["captcha"], "relay: captcha_audio")
        for _ in range(3):
            self.io.play(wav)
            raw = self.hear(secret="[captcha answer given]")
            if P.wants_repeat(raw):
                continue
            ans = P.parse_alnum(raw)
            if len(ans) >= 3:
                self.secrets.add(ans)
                self.db.answer_prompt(p["id"], ans)
                self.ev("citizen_turn", "[captcha answer given]")
                return
            self.say(T["retry"], "retry")

    # ---- result ---------------------------------------------------------------------------
    def finish(self, text, m):
        self.say(text + " " + T["bye"], m)

    def report(self, job):
        r, st = job.get("result") or {}, job["status"]
        num = P.digits_ml(self.db.get_case(self.case["id"]).get("case_number") or "")
        if st == "succeeded" and r.get("payment_status") == "confirmed":
            msg, m = "പേയ്മെന്റ് സ്ഥിരീകരിച്ചു. ഇത് പരീക്ഷണ മോഡിലാണ്.", "result: payment confirmed"
        elif st == "succeeded" and r.get("output_pdf"):
            msg, m = "ഫോം PDF തയ്യാറായി, കേസിൽ സൂക്ഷിച്ചിട്ടുണ്ട്. ഇത് ഒരിടത്തും സമർപ്പിച്ചിട്ടില്ല.", "result: pdf ready, not submitted"
        elif st == "succeeded" and r.get("stopped_before_submit"):
            msg, m = "ഫോം പൂരിപ്പിച്ച് അവസാന പേജ് വരെ എത്തി. സമർപ്പിച്ചിട്ടില്ല.", "result: stopped before submit"
        elif st == "succeeded":
            msg, m = "ജോലി പൂർത്തിയായി.", "result: done"
        elif st in ("failed", "cancelled"):
            code = (job.get("error") or st).split(":")[0][:40]
            msg, m = "ഇത് പൂർത്തിയാക്കാൻ കഴിഞ്ഞില്ല. ഒന്നും സമർപ്പിച്ചിട്ടില്ല, പണവും എടുത്തിട്ടില്ല എന്ന് ഉറപ്പ് പറയാൻ കഴിയില്ല; വിവരങ്ങൾ കേസിൽ ഉണ്ട്.", f"result: failed ({code})"
        else:
            msg, m = "ഇപ്പോഴും പ്രവർത്തനം തുടരുകയാണ്, ഫലം ഇതുവരെ ലഭിച്ചിട്ടില്ല (പെൻഡിംഗ്).", "result: pending"
        self.finish(f"{msg} കേസ് നമ്പർ: {num}.", m)
