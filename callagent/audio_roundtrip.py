"""Sarvam round trip: Bulbul says caller answers, Saaras transcribes, our parsers read them. Budget <= 40 Sarvam calls."""
import os
os.environ["SARVAM_CALL_BUDGET"] = "40"
import db as dbm
dbm.load_env()
import parsing as P
import speech
from engine import pick

NUMS = ["4829175036281", "1002003004005", "7364518290417", "9846012345"]
ML = P.ML_DIGITS


def say_digits(n):
    return ", ".join(ML[int(c)] for c in n)


def run(speaker=None):
    out = []
    for n in NUMS:
        text = speech.transcribe(speech.synthesize(say_digits(n), speaker))
        got = P.parse_digits(text)
        ok = sum(a == b for a, b in zip(n, got)) if len(got) == len(n) else 0
        out.append((n, got, got == n, ok))
        print("digits", n, "->", got, "EXACT" if got == n else "MISMATCH", "| stt:", text, flush=True)
    return out


def main():
    res = run()
    t = speech.transcribe(speech.synthesize("അതെ"))
    yes = P.parse_yes_no(t)
    print("yes ->", repr(t), yes)
    t2 = speech.transcribe(speech.synthesize("കെ.എസ്.ഇ.ബി ബിൽ അടയ്ക്കണം"))
    svc = pick(t2, [("kseb_bill_payment", ["KSEB bill payment", "കെഎസ്ഇബി ബിൽ", "kseb"]), ("kwa_water_bill", ["KWA water bill", "വാട്ടർ ബിൽ"])])
    print("service ->", repr(t2), svc)
    t3 = speech.transcribe(speech.synthesize("അല്ല"))
    print("no ->", repr(t3), P.parse_yes_no(t3))
    # second voice for variance
    try:
        res += run("ritu")
    except Exception as e:
        print("second voice skipped:", type(e).__name__)
    chars = sum(len(r[0]) for r in res)
    right = sum(sum(a == b for a, b in zip(r[0], r[1])) if len(r[1]) == len(r[0]) else 0 for r in res)
    print(f"whole numbers exact: {sum(r[2] for r in res)}/{len(res)}; positional digit accuracy {right}/{chars} ({100*right/chars:.1f}%)")
    print("SARVAM CALLS USED:", speech.CALLS)


main()
