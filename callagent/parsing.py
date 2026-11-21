"""Understanding what the citizen said: digits, yes/no, dates, phones, IFSC, "talk to a person".
Deterministic, no LLM. Ideas adapted from the older voice/ engine."""
import datetime as dt
import re
import unicodedata

ML_DIGITS = ["പൂജ്യം", "ഒന്ന്", "രണ്ട്", "മൂന്ന്", "നാല്", "അഞ്ച്", "ആറ്", "ഏഴ്", "എട്ട്", "ഒമ്പത്"]
EN_DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_OLD_CHILLU = {"ണ്‍": "ൺ", "ന്‍": "ൻ", "ര്‍": "ർ", "ല്‍": "ൽ", "ള്‍": "ൾ"}


def _stem(word: str) -> str:
    """Drop trailing chandrakkala / short u so ഒന്ന്, ഒന്നു and ഒന്ന compare equal."""
    return word.rstrip("്ു")


def _stems(*words: str) -> set[str]:
    return {_stem(w) for w in words}


_DIGIT_WORDS = {_stem(w): str(d) for d, w in enumerate(ML_DIGITS)} | {w: str(d) for d, w in enumerate(EN_DIGITS)}
_DIGIT_WORDS |= {_stem("ഒൻപത്"): "9", _stem("ഒമ്പത"): "9", _stem("സീറോ"): "0", "oh": "0", "o": "0",
                 _stem("പൂജ്യ"): "0", _stem("ഒരു"): "1", _stem("ഒന്നു"): "1", _stem("രണ്ടു"): "2"}
_REPEAT = {"double": 2, "triple": 3, "ഡബിൾ": 2, "ട്രിപ്പിൾ": 3}

_YES = _stems("അതെ", "അതേ", "ശരി", "ശരിയാണ്", "ഉവ്വ്", "ആം", "വേണം", "ഓക്കെ", "ഓക്കേ", "യെസ്",
              "yes", "yeah", "ok", "okay", "correct", "athe", "sheri", "sari")
_NO = _stems("അല്ല", "വേണ്ട", "ഇല്ല", "തെറ്റ്", "തെറ്റാണ്", "ശരിയല്ല", "നോ",
             "no", "nope", "wrong", "incorrect", "alla", "venda", "illa")
_PERSON_EXACT = {"person", "human", "operator", "ആൾ"}
_PERSON_PREFIX = ("മനുഷ്യ", "ആള")
_AGAIN = _stems("വീണ്ടും", "again", "repeat", "ആവർത്തിക്കൂ", "ഒന്നുകൂടി")


def tokens(text: str) -> list[str]:
    """Lower-cased words, every numeral its own token, punctuation dropped."""
    text = unicodedata.normalize("NFC", text).lower()
    for old, new in _OLD_CHILLU.items():
        text = text.replace(old, new)
    out = []
    for ch in text:
        digit = unicodedata.decimal(ch, None)
        if digit is not None:
            out.append(f" {digit} ")
        elif unicodedata.category(ch)[0] in "LM":
            out.append(ch)
        else:
            out.append(" ")
    return [_stem(t) for t in "".join(out).split()]


def parse_digits(text: str) -> str:
    """All digits said, in order, from numerals and Malayalam/English digit words. Other words ignored."""
    digits, repeat = "", 1
    for tok in tokens(text):
        if tok in _REPEAT:
            repeat = _REPEAT[tok]
            continue
        digit = tok if tok.isdigit() else _DIGIT_WORDS.get(tok)
        if digit is not None:
            digits += digit * repeat
        repeat = 1
    return digits


def parse_yes_no(text: str) -> bool | None:
    """True only if EVERY word is an affirmative ("not correct", "yes but ..." are not yes).
    False = a negative word and no affirmative. None = unclear."""
    toks = set(tokens(text))
    if toks and toks <= _YES:
        return True
    return False if toks & _NO and not toks & _YES else None


def wants_person(text: str) -> bool:
    return any(t in _PERSON_EXACT or t.startswith(_PERSON_PREFIX) for t in tokens(text))


def wants_repeat(text: str) -> bool:
    return any(t in _AGAIN for t in tokens(text))


def parse_phone(text: str) -> str | None:
    d = parse_digits(text)
    if len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d.startswith("0"):
        d = d[1:]
    return d if re.fullmatch(r"[6-9][0-9]{9}", d) else None


def parse_date(text: str, today: dt.date | None = None) -> str | None:
    """ISO date from '12/03/1980', '12 3 1980' or eight spoken digits (ddmmyyyy). Not in the future."""
    today = today or dt.date.today()
    m = re.search(r"(\d{1,2})\D+(\d{1,2})\D+(\d{4})", text)
    if m:
        d, mo, y = (int(x) for x in m.groups())
    else:
        digits = parse_digits(text)
        if len(digits) != 8:
            return None
        d, mo, y = int(digits[:2]), int(digits[2:4]), int(digits[4:])
    try:
        date = dt.date(y, mo, d)
    except ValueError:
        return None
    return date.isoformat() if dt.date(1900, 1, 1) <= date <= today else None


def _alnum(text: str) -> str:
    out = ""
    for tok in tokens(text):
        out += tok if tok.isdigit() else _DIGIT_WORDS.get(tok, tok)
    return out.upper()


def parse_ifsc(text: str) -> str | None:
    out = _alnum(text)
    return out if re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", out) else None


def parse_alnum(text: str) -> str:
    """Captcha characters: digit words become digits, other letters/digits are kept."""
    return _alnum(text)


def digits_ml(number: str) -> str:
    """Digit-by-digit read-back in Malayalam words."""
    return ", ".join(ML_DIGITS[int(d)] for d in number)


def spell(value: str) -> str:
    """Character-by-character read-back (digits as Malayalam words, letters as themselves)."""
    return ", ".join(ML_DIGITS[int(c)] if c.isdigit() else c for c in value if c != " ")
