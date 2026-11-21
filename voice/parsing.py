"""Understanding what the citizen said: digits, yes/no, "talk to a person". Deterministic, no LLM."""
import unicodedata

ML_DIGITS = ["പൂജ്യം", "ഒന്ന്", "രണ്ട്", "മൂന്ന്", "നാല്", "അഞ്ച്", "ആറ്", "ഏഴ്", "എട്ട്", "ഒമ്പത്"]
EN_DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

# Pre-Unicode-5.1 chillus (consonant + virama + ZWJ) -> atomic chillus
_OLD_CHILLU = {"ണ്\u200d": "ൺ", "ന്\u200d": "ൻ", "ര്\u200d": "ർ", "ല്\u200d": "ൽ", "ള്\u200d": "ൾ"}


def _stem(word: str) -> str:
    """Drop the trailing chandrakkala / short u so ഒന്ന്, ഒന്നു and ഒന്ന compare equal."""
    return word.rstrip("\u0d4d\u0d41")


def _stems(*words: str) -> set[str]:
    return {_stem(w) for w in words}


_DIGIT_WORDS = {_stem(w): str(d) for d, w in enumerate(ML_DIGITS)} | {w: str(d) for d, w in enumerate(EN_DIGITS)}
_DIGIT_WORDS |= {_stem("ഒൻപത്"): "9", _stem("സീറോ"): "0", "oh": "0", "o": "0"}
_REPEAT = {"double": 2, "triple": 3, "ഡബിൾ": 2, "ട്രിപ്പിൾ": 3}

_YES = _stems("അതെ", "അതേ", "ശരി", "ശരിയാണ്", "ഉവ്വ്", "ആം", "വേണം", "ഓക്കെ", "ഓക്കേ", "യെസ്",
              "yes", "yeah", "ok", "okay", "correct", "athe", "sheri", "sari")
_NO = _stems("അല്ല", "വേണ്ട", "ഇല്ല", "തെറ്റ്", "തെറ്റാണ്", "ശരിയല്ല", "നോ",
             "no", "nope", "wrong", "incorrect", "alla", "venda", "illa")
_PERSON_EXACT = {"person", "human", "operator", "ആൾ"}
_PERSON_PREFIX = ("മനുഷ്യ", "ആള")
_OTHER_SERVICE_EXACT = {"pension", "certificate", "ration", "passport", "water", "tax", "licence", "license"}
_OTHER_SERVICE_PREFIX = ("പെൻഷ", "സർട്ടിഫിക്ക", "റേഷ", "പാസ്പോർട്ട", "വെള്ളക്കര", "നികുതി", "ലൈസൻസ")


def tokens(text: str) -> list[str]:
    """Lower-cased words, with every numeral as its own token and punctuation dropped."""
    text = unicodedata.normalize("NFC", text).lower()
    for old, new in _OLD_CHILLU.items():
        text = text.replace(old, new)
    out = []
    for ch in text:
        digit = unicodedata.decimal(ch, None)
        if digit is not None:
            out.append(f" {digit} ")
        elif unicodedata.category(ch)[0] in "LM":  # letters and Malayalam vowel signs / virama
            out.append(ch)
        else:
            out.append(" ")
    return [_stem(t) for t in "".join(out).split()]


def parse_digits(text: str) -> str:
    """All digits said, in order, from numerals and Malayalam/English digit words. Other words are ignored."""
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
    """True = consent: every word of the reply is an affirmative ("not correct", "yes but ...", "correct it" are not).
    False = a negative word and no affirmative one. None = unclear (anything else)."""
    toks = set(tokens(text))
    if toks and toks <= _YES:
        return True
    return False if toks & _NO and not toks & _YES else None


def wants_person(text: str) -> bool:
    return any(t in _PERSON_EXACT or t.startswith(_PERSON_PREFIX) for t in tokens(text))


def wants_other_service(text: str) -> bool:
    """A few well-known services this prototype does not do (it only pays KSEB bills). Not an intent engine."""
    return any(t in _OTHER_SERVICE_EXACT or t.startswith(_OTHER_SERVICE_PREFIX) for t in tokens(text))


def digits_ml(number: str) -> str:
    """Digit-by-digit read-back in Malayalam words."""
    return ", ".join(ML_DIGITS[int(d)] for d in number)
