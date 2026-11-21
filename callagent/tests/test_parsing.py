import datetime as dt
import parsing as P


def test_digits_malayalam_english_numerals():
    assert P.parse_digits("ഒന്ന് രണ്ട് മൂന്ന് നാല് അഞ്ച് ആറ് ഏഴ് എട്ട് ഒമ്പത് പൂജ്യം") == "1234567890"
    assert P.parse_digits("one two 3 four, double seven") == "123477"
    assert P.parse_digits("1234 5678") == "12345678"
    assert P.parse_digits("൧൨൩") == "123"


def test_yes_no_strict():
    assert P.parse_yes_no("അതെ") is True
    assert P.parse_yes_no("yes") is True
    assert P.parse_yes_no("yes but change it") is None
    assert P.parse_yes_no("not correct") is None or P.parse_yes_no("not correct") is False
    assert P.parse_yes_no("അല്ല") is False
    assert P.parse_yes_no("hmm") is None


def test_phone_date_ifsc():
    assert P.parse_phone("9 8 4 6 0 1 2 3 4 5") == "9846012345"
    assert P.parse_phone("+91 98460 12345") == "9846012345"
    assert P.parse_phone("12345") is None
    assert P.parse_date("12/03/1980") == "1980-03-12"
    assert P.parse_date("1 2 0 3 1 9 8 0") == "1980-03-12"
    assert P.parse_date("31/02/1980") is None
    assert P.parse_date("01/01/2999", today=dt.date(2026, 1, 1)) is None
    assert P.parse_ifsc("SBIN 0001234") == "SBIN0001234"
    assert P.parse_ifsc("sbin zero zero zero one two three four") == "SBIN0001234"
    assert P.parse_ifsc("ABCD1234567") is None


def test_readback_is_digit_by_digit():
    assert P.digits_ml("120") == "ഒന്ന്, രണ്ട്, പൂജ്യം"
    assert P.spell("SB1") == "S, B, ഒന്ന്"
