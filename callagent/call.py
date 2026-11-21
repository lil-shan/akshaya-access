"""Inbound call agent. python call.py --text | --script FILE | --audio  [--phone 9XXXXXXXXX] [--tag-e2e]
Never prints secrets. Spoken OTP/password/captcha turns are shown only as labels like [OTP given]."""
import argparse
import os
import re
import sys
import time
from pathlib import Path

import db as dbm
from engine import Call, Hangup

MOCK = Path(__file__).resolve().parent.parent / "automation/mock_portals/edistrict"


class TextIO:
    """Typed citizen. Lines come from stdin (--text) or a script file (--script)."""
    def __init__(self, lines=None):
        self.lines, self.transcript = lines, []

    def say(self, text):
        print("AGENT:", text, flush=True)
        self.transcript.append(("agent", text))

    def play(self, wav):
        print("AGENT: [plays portal audio captcha]", flush=True)

    def _next(self):
        if self.lines is None:
            try:
                return input("CITIZEN> ")
            except EOFError:
                raise Hangup
        if not self.lines:
            raise Hangup
        return self.lines.pop(0)

    def hear(self, label=None):
        line = self._next()
        if os.environ.get("CALLAGENT_TEST_HOOKS") == "1":  # integration tests only
            line = self._hook(line)
        print("CITIZEN:", label or line, flush=True)
        self.transcript.append(("citizen", label or line))
        return line

    @staticmethod
    def _hook(line):
        if "{{SMS_OTP}}" in line:
            for _ in range(60):
                found = re.findall(r"OTP is (\d+)", (MOCK / "sms.log").read_text()) if (MOCK / "sms.log").exists() else []
                if found:
                    return line.replace("{{SMS_OTP}}", found[-1])
                time.sleep(1)
        if "{{CAPTCHA_ANSWER}}" in line:
            return line.replace("{{CAPTCHA_ANSWER}}", (MOCK / "captcha_answer.txt").read_text().strip())
        return line


def main(argv=None):
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", action="store_true")
    g.add_argument("--script")
    g.add_argument("--audio", action="store_true")
    ap.add_argument("--phone")
    ap.add_argument("--tag-e2e", action="store_true", help="mark the case data _e2e=true (test cleanup)")
    a = ap.parse_args(argv)
    dbm.load_env()
    if a.audio:
        from speech import AudioIO
        io = AudioIO()
    elif a.script:
        io = TextIO([ln.rstrip("\n") for ln in Path(a.script).read_text().splitlines() if ln.strip() and not ln.startswith("#")])
    else:
        io = TextIO()
    case = Call(io, dbm.Db(), phone=a.phone, extra_data={"_e2e": True} if a.tag_e2e else None).run()
    print("CASE:", case["case_number"] if case else "none")


if __name__ == "__main__":
    main()
