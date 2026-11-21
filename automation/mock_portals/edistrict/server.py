"""MOCK e-District Kerala portal (income certificate). Local only, nothing real.
Flow: / mobile -> /otp -> /captcha (image + audio) -> /form -> /review (Submit must NOT be clicked by automation).
Test hooks: sms.log (the 'SMS' with OTP), captcha_answer.txt (known answer, tests only)."""
import io, json, math, os, random, struct, wave, html, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
import tts
from PIL import Image, ImageDraw, ImageFont

D = os.path.dirname(os.path.abspath(__file__))
FIELDS = json.load(open(os.path.join(D, "fields.json")))
S = {"otp": None, "cap": None, "ok_otp": False, "ok_cap": False, "data": {}, "submitted": False}
DTMF = {"1": (697, 1209), "2": (697, 1336), "3": (697, 1477), "4": (770, 1209), "5": (770, 1336),
        "6": (770, 1477), "7": (852, 1209), "8": (852, 1336), "9": (852, 1477), "0": (941, 1336)}

def audio(code, lang="en"):
    """Spoken digits via Sarvam Bulbul (cached, see tts.py); fallback when no key/call fails: a distinct two-tone (DTMF) beep per digit."""
    spoken = tts.speak_digits(code, lang)
    if spoken: return spoken
    buf, rate = io.BytesIO(), 8000
    w = wave.open(buf, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    for ch in code:
        f1, f2 = DTMF[ch]
        w.writeframes(b"".join(struct.pack("<h", int(8000 * (math.sin(2*math.pi*f1*i/rate) + math.sin(2*math.pi*f2*i/rate)) / 2))
                               for i in range(int(rate * .4))) + b"\0\0" * int(rate * .2))
    w.close(); return buf.getvalue()

def image(code):
    im = Image.new("RGB", (200, 70), "white"); d = ImageDraw.Draw(im)
    for _ in range(8): d.line([(random.randint(0, 200), random.randint(0, 70)) for _ in range(2)], fill="gray", width=1)
    try: font = ImageFont.load_default(size=36)
    except TypeError: font = ImageFont.load_default()
    for i, ch in enumerate(code): d.text((15 + i * 34, 12 + random.randint(-5, 5)), ch, fill="black", font=font)
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()

def page(title, body):
    return f"<!doctype html><html><head><meta charset=utf-8><title>{title}</title></head><body><h2>MOCK e-District Kerala (test portal)</h2><h3>{title}</h3>{body}</body></html>".encode()

def field_html(f):
    k = f["key"]; req = " required" if f.get("required") else ""
    if f["type"] == "select":
        o = "".join(f"<option>{html.escape(x)}</option>" for x in f.get("options", []))
        inp = f"<select name={k}{req}>{o}</select>"
    else:
        t = {"date": "date", "number": "number"}.get(f["type"], "text")
        inp = f"<input type={t} name={k}{req}>"
    return f"<p><label>{html.escape(f['label'])} {inp}</label></p>"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, body, ct="text/html", code=200):
        self.send_response(code); self.send_header("Content-Type", ct); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/": S.update(otp=None, cap=None, ok_otp=False, ok_cap=False, data={}, submitted=False)
        if p == "/":
            self.send(page("Login", "<form method=post action=/send-otp><label>Mobile number <input name=mobile id=mobile pattern='[0-9]{10}' required></label><button id=send-otp>Send OTP</button></form>"))
        elif p == "/otp":
            self.send(page("Enter OTP", "<form method=post action=/verify-otp><label>OTP <input name=otp id=otp required></label><button id=verify-otp>Verify</button></form>"))
        elif p == "/captcha":
            S["cap"] = "".join(random.choices("0123456789", k=5))
            open(os.path.join(D, "captcha_answer.txt"), "w").write(S["cap"])  # test-only hook
            self.send(page("Captcha", "<form method=post action=/verify-captcha><img id=captcha-image src=/captcha.png alt=captcha><p><audio id=captcha-audio controls src=/captcha.wav></audio> <a id=captcha-audio-link href=/captcha.wav>Listen (audio captcha)</a> <a id=captcha-audio-ml href=/captcha-ml.wav>Malayalam</a></p><label>Captcha <input name=captcha id=captcha required></label><button id=verify-captcha>Continue</button></form>"))
        elif p == "/captcha.png": self.send(image(S["cap"] or "00000"), "image/png")
        elif p == "/captcha.wav": self.send(audio(S["cap"] or "00000"), "audio/wav")
        elif p == "/captcha-ml.wav": self.send(audio(S["cap"] or "00000", "ml"), "audio/wav")
        elif p == "/form" and S["ok_cap"]:
            self.send(page("Income certificate application", "<form method=post action=/review-post>" + "".join(map(field_html, FIELDS)) + "<button id=to-review>Save and review</button></form>"))
        elif p == "/review" and S["ok_cap"]:
            rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>" for k, v in S["data"].items())
            self.send(page("Review", f"<table border=1 id=review-table>{rows}</table><form method=post action=/submit><button id=final-submit>Submit application</button></form>"))
        elif p == "/done": self.send(page("Submitted", "<p id=submitted>Application submitted (mock).</p>"))
        else: self.send(page("Not allowed", "<p>Complete login first.</p>"), code=403)
    def do_POST(self):
        q = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()).items()}
        p = self.path
        def go(to): self.send_response(303); self.send_header("Location", to); self.end_headers()
        if p == "/send-otp":
            S["otp"] = f"{random.randint(0, 999999):06d}"
            open(os.path.join(D, "sms.log"), "a").write(f"[MOCK SMS to ******{q.get('mobile','')[-4:]}] Your e-District OTP is {S['otp']}\n")
            go("/otp")
        elif p == "/verify-otp":
            if q.get("otp") == S["otp"]: S["ok_otp"] = True; go("/captcha")
            else: self.send(page("Wrong OTP", "<p id=error>Invalid OTP</p><a href=/otp>Retry</a>"), code=400)
        elif p == "/verify-captcha":
            if S["ok_otp"] and q.get("captcha") == S["cap"]: S["ok_cap"] = True; go("/form")
            else: self.send(page("Wrong captcha", "<p id=error>Invalid captcha</p><a href=/captcha>Retry</a>"), code=400)
        elif p == "/review-post": S["data"] = q; go("/review")
        elif p == "/submit": S["submitted"] = True; open(os.path.join(D, "SUBMITTED"), "w").write("1"); go("/done")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    HTTPServer(("127.0.0.1", port), H).serve_forever()
