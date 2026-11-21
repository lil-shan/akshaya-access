import pytest

from parsing import digits_ml, parse_digits, parse_yes_no, wants_other_service, wants_person

FIXTURE = "1155432100987"


@pytest.mark.parametrize(
    "said",
    [
        "1155432100987",
        "11554 32100 987",
        "1155-4321-00987.",
        "ഒന്ന് ഒന്ന് അഞ്ച് അഞ്ച് നാല് മൂന്ന് രണ്ട് ഒന്ന് പൂജ്യം പൂജ്യം ഒമ്പത് എട്ട് ഏഴ്",
        "ഒന്ന്, ഒന്ന്, അഞ്ച്, അഞ്ച്, നാല്, മൂന്ന്, രണ്ട്, ഒന്ന്, പൂജ്യം, പൂജ്യം, ഒൻപത്, എട്ട്, ഏഴ്",
        "one one five five four three two one zero zero nine eight seven",
        "One One Five Five Four Three Two One Oh Oh Nine Eight Seven",
        "double one double five four three two one double zero nine eight seven",
        "എന്റെ നമ്പർ 11554 മൂന്ന് രണ്ട് one zero zero 987 ആണ്",
    ],
)
def test_parse_digits_reads_numerals_malayalam_and_english_words(said):
    assert parse_digits(said) == FIXTURE


def test_parse_digits_accepts_old_style_chillu_and_u_ending():
    # "ഒന്‍പത്" written with the pre-5.1 chillu sequence, "ഒന്നു" with a full u
    assert parse_digits("ഒന\u0d4d\u200dപത് ഒന്നു") == "91"


@pytest.mark.parametrize("said, expected", [("1155", "1155"), ("one two three", "123"), ("11554321009870", "11554321009870")])
def test_parse_digits_returns_wrong_length_as_is_for_the_caller_to_reject(said, expected):
    assert parse_digits(said) == expected
    assert len(parse_digits(said)) != 13


@pytest.mark.parametrize("said", ["", "അതെ", "hello there"])
def test_parse_digits_without_digits_is_empty(said):
    assert parse_digits(said) == ""


@pytest.mark.parametrize("said", ["അതെ", "അതേ.", "ശരി", "ശരിയാണ്", "ഉവ്വ്", "ആം", "yes", "Yes, correct", "ok", "athe"])
def test_yes(said):
    assert parse_yes_no(said) is True


@pytest.mark.parametrize("said", ["അല്ല", "വേണ്ട", "ഇല്ല", "തെറ്റാണ്", "ശരിയല്ല", "no", "No!", "wrong", "alla"])
def test_no(said):
    assert parse_yes_no(said) is False


@pytest.mark.parametrize("said", ["", "ഹലോ", "maybe", "yes no", "അതെ അല്ല", "1155"])
def test_unclear_yes_no_is_none(said):
    assert parse_yes_no(said) is None


@pytest.mark.parametrize("said", ["അതെ, ശരിയാണ്", "yes yes", "Ok, correct.", "ശരി ശരി"])
def test_a_reply_made_only_of_affirmative_words_is_yes(said):
    assert parse_yes_no(said) is True


@pytest.mark.parametrize("said", [
    "not correct", "I am not sure it is correct", "I want to correct the number",  # review round 1, finding 1
    "yes but the amount is wrong", "correct it", "ok wait", "yes 4826", "yes, 640 is too much",
    "ശരി അല്ല", "ശരിയല്ല, അതെ", "അതെ പക്ഷേ തുക തെറ്റാണ്", "നമ്പർ ശരിയാക്കണം", "എനിക്ക് പെൻഷൻ വേണം",
])
def test_corrections_negations_and_qualified_replies_are_never_yes(said):
    assert parse_yes_no(said) is not True


@pytest.mark.parametrize("said", ["no, that is wrong", "ഇല്ല, തെറ്റാണ്", "അത് ശരിയല്ല"])
def test_a_reply_with_a_negative_word_and_no_affirmative_word_is_no(said):
    assert parse_yes_no(said) is False


@pytest.mark.parametrize("said", [
    "എനിക്ക് പെൻഷൻ സർട്ടിഫിക്കറ്റ് വേണം", "പെൻഷന്റെ കാര്യം അറിയണം", "റേഷൻ കാർഡ്", "വരുമാന സർട്ടിഫിക്കറ്റിന് അപേക്ഷിക്കണം",
    "I need a pension certificate", "Ration card please", "water bill", "passport",
])
def test_wants_other_service(said):
    assert wants_other_service(said)


@pytest.mark.parametrize("said", ["", "അതെ", "1155432100987", "ഹലോ", "എന്റെ കറന്റ് ബിൽ അടയ്ക്കണം", "I want to pay my electricity bill"])
def test_does_not_want_other_service(said):
    assert not wants_other_service(said)


@pytest.mark.parametrize(
    "said",
    ["മനുഷ്യൻ", "എനിക്ക് ഒരു മനുഷ്യനോട് സംസാരിക്കണം", "ഒരു ആളെ തരൂ", "ആളോട് സംസാരിക്കണം", "I want a person", "HUMAN please"],
)
def test_wants_person(said):
    assert wants_person(said)


@pytest.mark.parametrize("said", ["അതെ", "1155432100987", "personal", "no"])
def test_does_not_want_person(said):
    assert not wants_person(said)


def test_digits_ml_reads_back_each_digit_as_a_malayalam_word():
    assert digits_ml("1050") == "ഒന്ന്, പൂജ്യം, അഞ്ച്, പൂജ്യം"
    assert parse_digits(digits_ml(FIXTURE)) == FIXTURE
