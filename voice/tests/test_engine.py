import pytest

from backend import BackendError
from engine import Engine
from fakes import FakeBackend, FakeClock, ScriptedCitizen
from parsing import digits_ml

NUMBER = "1155432100987"
NUMBER_ML = "ഒന്ന് ഒന്ന് അഞ്ച് അഞ്ച് നാല് മൂന്ന് രണ്ട് ഒന്ന് പൂജ്യം പൂജ്യം ഒമ്പത് എട്ട് ഏഴ്"
NOTHING_DUE = "1150000000000"
YES, NO = "അതെ", "അല്ല"


HEARD_NUMBER = (f"കൺസ്യൂമർ നമ്പർ {NUMBER}", f"consumer number {NUMBER}")
HEARD_YES, HEARD_NO, HEARD_UNCLEAR = ("അതെ", "yes"), ("അല്ല", "no"), ("[തിരിച്ചറിയാത്ത സംസാരം]", "[unrecognised speech]")
HEARD_PERSON = ("ഒരാളോട് സംസാരിക്കണമെന്ന് പറഞ്ഞു", "asked for a person")
HEARD_SERVICE = ("മറ്റൊരു സേവനം ചോദിച്ചു", "asked for another service")
END = "/calls/call-1/end"
STATUS = "/tools/payment_status/pay-1"


def run(*lines, unheard=(), poll_interval=2, poll_timeout=60, **backend_options):
    """Run one whole call with the citizen saying `lines`. Returns (outcome, fake backend, io, sleeps)."""
    fake, io, clock = FakeBackend(**backend_options), ScriptedCitizen(*lines, unheard=unheard), FakeClock()
    engine = Engine(fake.client(), io, poll_interval=poll_interval, poll_timeout=poll_timeout, sleep=clock.sleep, clock=clock.time)
    return engine.run("+919999904321", "simulator"), fake, io, clock.sleeps


def citizen_lines(fake, io):
    """Everything of the citizen that reached the backend or the screen, as (text, text_en)."""
    return ([(e["text"], e.get("text_en")) for e in fake.said("citizen_said")]
            + [(text, text_en) for kind, text, text_en, _ in io.shown if kind == "citizen"])


def interrupt_when(fake, wanted):
    """Ctrl-C (KeyboardInterrupt) inside the first backend request for which wanted(path, body) is true."""
    def hook(path, body):
        if wanted(path, body):
            fake.on_request = None
            raise KeyboardInterrupt
    fake.on_request = hook


def test_opening_says_ai_demo_simulated_and_never_otp_pin_aadhaar_in_malayalam_and_english():
    _, fake, io, _ = run()
    opening = fake.said()[0]
    for word in ["എ.ഐ.", "ഡെമോ", "സിമുലേറ്റഡ്", "ഒ.ടി.പി.", "പിൻ", "ആധാർ", "ചോദിക്കില്ല"]:
        assert word in opening["text"]
    for word in ["AI assistant", "demo", "SIMULATED", "never ask", "OTP", "PIN", "Aadhaar"]:
        assert word in opening["text_en"]
    assert "ബില്ലും പണമടയ്ക്കലും" in opening["text"] and "bills and payments" in opening["text_en"]  # finding 17
    assert "സ്പീച്ച് സേവനം" in opening["text"] and "speech service" in opening["text_en"]  # finding 3
    assert io.shown[0][3] is True  # spoken in both languages in audio mode


def test_happy_path_pays_after_both_confirmations():
    outcome, fake, _, sleeps = run(NUMBER_ML, YES, "ശരി")

    assert outcome == "paid" and fake.outcome == "paid"
    assert fake.bodies("/calls") == [{"caller_phone": "+919999904321", "channel": "simulator", "language": "ml"}]
    assert fake.bodies("/tools/fetch_bill") == [
        {"call_id": "call-1", "biller": "KSEB", "consumer_number": NUMBER, "number_confirmed": True}]
    assert fake.bodies("/tools/confirm_amount") == [
        {"call_id": "call-1", "bill_id": "KSEB-SIM-0001", "citizen_confirmed": True}]
    assert fake.bodies("/tools/start_payment") == [{"call_id": "call-1", "bill_id": "KSEB-SIM-0001"}]
    tools = [p for p in fake.paths() if p.startswith("/tools/")]
    assert tools == ["/tools/fetch_bill", "/tools/confirm_amount", "/tools/start_payment"] + ["/tools/payment_status/pay-1"] * 3
    assert sleeps == [2, 2]
    assert fake.states() == ["collecting_number", "confirming_number", "fetching_bill", "confirming_amount", "paying", "done"]
    assert fake.paths()[-1] == "/calls/call-1/end"


def test_happy_path_reads_back_number_digit_by_digit_then_name_and_amount_then_reference():
    _, fake, _, _ = run(NUMBER, YES, YES)
    agent = fake.said()
    readback = next(e for e in agent if digits_ml(NUMBER) in e["text"])
    assert "1 1 5 5 4 3 2 1 0 0 9 8 7" in readback["text_en"]
    bill = next(e for e in agent if "രാജൻ കെ" in e["text"])
    assert "640 രൂപ" in bill["text"] and "Rajan K" in bill["text_en"] and "640" in bill["text_en"]
    assert "SIMULATED" in bill["text_en"]
    assert "SIMREF123456" in agent[-1]["text"] and "SIMREF123456" in agent[-1]["text_en"]
    assert "സ്ഥിരീകരിച്ചു" in agent[-1]["text"] and "confirmed" in agent[-1]["text_en"]


def test_pin_step_says_keypad_with_bank_and_that_the_assistant_cannot_hear_it():
    _, fake, io, _ = run(NUMBER, YES, YES)
    pin_line = next(e for e in fake.said() if "123PAY" in e["text_en"])
    assert "കീപാഡിൽ" in pin_line["text"] and "ബാങ്കിന്റെ" in pin_line["text"] and "കേൾക്കാൻ കഴിയില്ല" in pin_line["text"]
    assert "keypad" in pin_line["text_en"] and "bank" in pin_line["text_en"] and "cannot hear" in pin_line["text_en"]
    assert ("agent", pin_line["text"], pin_line["text_en"], True) in io.shown


def test_every_line_is_posted_with_malayalam_text_and_english_text_en():
    _, fake, _, _ = run(NUMBER_ML, YES, YES)
    lines = fake.said("agent_said") + fake.said("citizen_said")
    assert len(fake.said("citizen_said")) == 3
    assert all(e["text"] and e["text_en"] for e in lines)
    assert [(e["text"], e["text_en"]) for e in fake.said("citizen_said")] == [HEARD_NUMBER, HEARD_YES, HEARD_YES]


def test_correction_asks_for_the_number_again_and_fetches_only_the_confirmed_one():
    outcome, fake, _, _ = run("1155432100988", NO, NUMBER, YES, YES)
    assert outcome == "paid"
    assert [b["consumer_number"] for b in fake.bodies("/tools/fetch_bill")] == [NUMBER]
    assert fake.states()[:4] == ["collecting_number", "confirming_number", "collecting_number", "confirming_number"]


def test_wrong_length_number_is_rejected_and_asked_again():
    outcome, fake, _, _ = run("11554321", NUMBER, YES, YES)
    assert outcome == "paid"
    assert any("13 digits" in e["text_en"] and "8" in e["text_en"] for e in fake.said())


@pytest.mark.parametrize("lines", [("1155", "one two three"), ("1155432100988", NO, "1155432100989", NO), ("1155", NUMBER, NO)])
def test_two_failed_number_attempts_hand_off_as_number_unclear(lines):
    outcome, fake, io, _ = run(*lines, YES, YES)
    assert outcome == "handed_off" and fake.outcome == "handed_off"
    assert fake.handoff["reason"] == "number_unclear"
    assert "/tools/fetch_bill" not in fake.paths()
    assert fake.states()[-1] == "handed_off"
    assert "നാല്, എട്ട്, രണ്ട്, ഏഴ്" in fake.said()[-1]["text"]
    assert io.lines == [YES, YES]  # stopped listening after the hand-off


def test_unknown_number_counts_as_a_failed_attempt():
    outcome, fake, _, _ = run("1159999999999", YES, NUMBER, YES, YES)
    assert outcome == "paid"
    assert any("could not find a bill" in e["text_en"] for e in fake.said())
    outcome, fake, _, _ = run("1159999999999", YES, "1158888888888", YES)
    assert outcome == "handed_off" and fake.handoff["reason"] == "number_unclear"


def test_nothing_due_says_so_and_never_starts_a_payment():
    outcome, fake, _, _ = run(NOTHING_DUE, YES)
    assert outcome == "nothing_due" and fake.outcome == "nothing_due"
    assert "/tools/start_payment" not in fake.paths() and "/tools/confirm_amount" not in fake.paths()
    last = fake.said()[-1]
    assert "അബ്ദുൾ ഖാദർ" in last["text"] and "ബാക്കിയില്ല" in last["text"] and "no amount due" in last["text_en"]
    assert fake.states()[-1] == "done"


def test_failed_payment_is_reported_as_failed():
    outcome, fake, _, _ = run(NUMBER, YES, YES, payment_statuses=["pending", "failed"])
    assert outcome == "payment_failed" and fake.outcome == "payment_failed"
    last = fake.said()[-1]
    assert "പരാജയപ്പെട്ടു" in last["text"] and "failed" in last["text_en"]
    assert "സ്ഥിരീകരിച്ചു" not in last["text"]


def test_payment_still_pending_after_timeout_is_said_as_pending():
    outcome, fake, _, sleeps = run(NUMBER, YES, YES, payment_statuses=["pending"])
    assert outcome == "payment_pending" and fake.outcome == "payment_pending"
    assert sleeps == [2] * 30  # every 2 s, up to 60 s
    assert fake.paths().count("/tools/payment_status/pay-1") == 31
    last = fake.said()[-1]
    assert "പെൻഡിംഗ്" in last["text"] and "PENDING" in last["text_en"]
    assert "പരാജയപ്പെട്ടു" not in last["text"] and "അടച്ചു" not in last["text"]
    assert "call back" not in last["text_en"] and "വിളിച്ച്" not in last["text"]  # finding 9: no way to look it up later


@pytest.mark.parametrize("lines", [
    ("എനിക്ക് ഒരു മനുഷ്യനോട് സംസാരിക്കണം",),
    (NUMBER, "ഒരു ആളെ തരൂ"),
    (NUMBER, YES, "I want to talk to a person"),
])
def test_asking_for_a_person_at_any_point_hands_off_as_citizen_request(lines):
    outcome, fake, _, _ = run(*lines, YES)
    assert outcome == "handed_off" and fake.outcome == "handed_off"
    assert fake.handoff["reason"] == "citizen_request"
    assert "/tools/start_payment" not in fake.paths()
    assert (fake.said("citizen_said")[-1]["text"], fake.said("citizen_said")[-1]["text_en"]) == HEARD_PERSON


def test_guard_409_on_start_payment_is_explained_and_handed_off_without_retry():
    outcome, fake, _, _ = run(NUMBER, YES, YES, force_guard={"/tools/start_payment": "payment_already_started"})
    assert outcome == "handed_off"
    assert fake.paths().count("/tools/start_payment") == 1
    assert "/tools/payment_status/pay-1" not in fake.paths()
    assert fake.handoff["reason"] == "payment_problem" and "payment_already_started" in fake.handoff["note"]
    explained = fake.said()[-1]
    assert "സുരക്ഷാ പരിശോധന" in explained["text"] and "safety check" in explained["text_en"]
    assert "പിൻ" not in explained["text"]  # never reached the PIN step


def test_guard_409_on_fetch_bill_is_handed_off_without_retry():
    outcome, fake, _, _ = run(NUMBER, YES, YES, force_guard={"/tools/fetch_bill": "number_not_confirmed"})
    assert outcome == "handed_off"
    assert fake.paths().count("/tools/fetch_bill") == 1
    assert fake.handoff["reason"] == "other" and "number_not_confirmed" in fake.handoff["note"]


def test_unclear_yes_no_is_asked_once_more():
    outcome, fake, _, _ = run(NUMBER, "ഹലോ", YES, "എന്ത്?", YES)
    assert outcome == "paid"
    assert sum("only yes or no" in e["text_en"] for e in fake.said()) == 2


def test_twice_unclear_on_amount_is_treated_as_no_and_nothing_is_paid():
    outcome, fake, _, _ = run(NUMBER, YES, "ഹലോ", "ഹലോ")
    assert outcome == "abandoned"
    assert "/tools/start_payment" not in fake.paths()
    assert fake.bodies("/tools/confirm_amount")[0]["citizen_confirmed"] is False


def test_twice_unclear_on_number_is_treated_as_no_and_number_is_asked_again():
    outcome, fake, _, _ = run(NUMBER, "ഹലോ", "ഹലോ", NUMBER, YES, YES)
    assert outcome == "paid"
    assert fake.states()[:3] == ["collecting_number", "confirming_number", "collecting_number"]


def test_saying_no_to_the_amount_ends_without_payment():
    outcome, fake, _, _ = run(NUMBER, YES, "വേണ്ട")
    assert outcome == "abandoned" and fake.outcome == "abandoned"
    assert "/tools/start_payment" not in fake.paths()
    assert "No payment has been made" in fake.said()[-1]["text_en"]


def test_hang_up_ends_the_call_as_abandoned():
    outcome, fake, _, _ = run(NUMBER)
    assert outcome == "abandoned" and fake.outcome == "abandoned"
    assert fake.paths()[-1] == "/calls/call-1/end"


def test_hang_up_while_waiting_for_the_bank_ends_the_call_as_payment_pending():
    def hang_up(_seconds):
        raise KeyboardInterrupt

    fake = FakeBackend(payment_statuses=["pending"])
    outcome = Engine(fake.client(), ScriptedCitizen(NUMBER, YES, YES), sleep=hang_up).run("+919999904321", "simulator")
    assert outcome == "payment_pending" and fake.outcome == "payment_pending"


def test_pin_like_digits_said_by_the_citizen_are_never_posted_or_shown():
    _, fake, io, _ = run(NUMBER, "എന്റെ പിൻ 4 8 2 6 ആണ്", YES, "otp four eight two six one nine", YES)
    everything = " ".join(f"{e['text']} {e.get('text_en', '')}" for e in fake.events)
    everything += " ".join(f"{text} {text_en}" for _, text, text_en, _ in io.shown)
    assert "4 8 2 6" not in everything and "four eight two six" not in everything and "4826" not in everything
    assert [e["text_en"] for e in fake.said("citizen_said")].count("[unrecognised speech]") == 2


def test_asking_for_a_person_is_still_understood_when_the_line_has_hidden_digits():
    outcome, fake, _, _ = run(NUMBER, "പിൻ 4826, ഒരു ആളെ തരൂ")
    assert outcome == "handed_off" and fake.handoff["reason"] == "citizen_request"
    assert "4826" not in fake.said("citizen_said")[-1]["text"]


def test_citizen_is_never_listened_to_during_or_after_the_pin_step():
    outcome, _, io, _ = run(NUMBER, YES, YES, "4826", "4826")
    assert outcome == "paid"
    assert io.lines == ["4826", "4826"]


# --- review round 1 ---

CORRECTIONS = ["not correct", "I am not sure it is correct", "I want to correct the number", "yes but change the last digit",
               "ശരി അല്ല", "അതെ പക്ഷേ തെറ്റുണ്ട്", "നമ്പർ ശരിയാക്കണം"]


@pytest.mark.parametrize("reply", CORRECTIONS)
def test_a_correction_or_negation_after_the_number_read_back_never_fetches_a_bill(reply):  # finding 1
    outcome, fake, _, _ = run(NUMBER, reply, reply)
    assert outcome == "abandoned"
    assert not [p for p in fake.paths() if p.startswith("/tools/")]


@pytest.mark.parametrize("reply", CORRECTIONS)
def test_a_correction_or_negation_after_the_amount_read_back_never_starts_a_payment(reply):  # finding 1
    outcome, fake, _, _ = run(NUMBER, YES, reply, reply)
    assert outcome == "abandoned"
    assert "/tools/start_payment" not in fake.paths()
    assert [b["citizen_confirmed"] for b in fake.bodies("/tools/confirm_amount")] == [False]


def test_citizen_lines_are_posted_and_shown_only_as_what_was_understood():  # finding 3
    _, fake, io, _ = run(f"എന്റെ നമ്പർ {NUMBER} ആണ്, വീട് കോഴിക്കോട്", "ഹലോ, എന്റെ പേര് രാജൻ", "ശരിയാണ്", "തെറ്റാണ്")
    assert citizen_lines(fake, io) == [HEARD_NUMBER, HEARD_UNCLEAR, HEARD_YES, HEARD_NO] * 2


@pytest.mark.parametrize("secret", [
    "my pin is forty eight twenty six",  # number words the digit parser does not know
    "എന്റെ പിൻ നാല്പത്തെട്ട് ഇരുപത്തിയാറ്",
    f"{NUMBER} and my otp is 482613",
    "otp 48 26 13",
    "1155432100 987 എന്റെ ആധാർ 2345 6789 0123",
])
def test_raw_citizen_speech_never_reaches_the_backend_or_the_screen(secret):  # finding 3
    _, fake, io, _ = run(secret, NUMBER, secret, YES, secret, YES)
    assert len(citizen_lines(fake, io)) == 12
    assert set(citizen_lines(fake, io)) == {HEARD_NUMBER, HEARD_YES, HEARD_UNCLEAR}


def test_a_13_digit_number_is_posted_as_the_number_only_not_with_the_rest_of_the_sentence():  # finding 3
    _, fake, io, _ = run(f"{NUMBER} my mother's name is Ammini")
    assert citizen_lines(fake, io) == [HEARD_NUMBER] * 2


@pytest.mark.parametrize("unheard, not_listened_to, tools_called", [
    ("I am an AI assistant", [NUMBER, YES, YES], []),
    ("The number I heard", [YES, YES], []),
    ("The bill is in the name", [YES], ["/tools/fetch_bill"]),
])
def test_when_the_opening_or_a_read_back_is_not_played_no_answer_is_taken_and_the_call_is_handed_off(
        unheard, not_listened_to, tools_called):  # finding 5
    outcome, fake, io, _ = run(NUMBER, YES, YES, unheard=[unheard])
    assert outcome == "handed_off" and fake.handoff["reason"] == "other"
    assert io.lines == not_listened_to
    assert [p for p in fake.paths() if p.startswith("/tools/")] == tools_called + ["/tools/handoff"]
    unplayed = next(i for i, e in enumerate(fake.said()) if unheard in e["text_en"])
    assert "NOT PLAYED" in fake.said()[unplayed + 1]["text_en"]  # the transcript does not claim it was spoken


def test_a_line_that_is_played_is_not_marked_as_not_played():  # finding 5
    _, fake, _, _ = run(NUMBER, YES, YES)
    assert not any("NOT PLAYED" in e["text_en"] for e in fake.said())


def test_an_unplayed_line_after_the_payment_started_does_not_stop_the_status_check():  # finding 5
    outcome, fake, _, _ = run(NUMBER, YES, YES, unheard=["UPI 123PAY line"])
    assert outcome == "paid" and fake.handoff is None


def test_backend_error_mid_call_tells_the_citizen_and_closes_the_call():  # finding 8
    fake, io = FakeBackend(fail={"/tools/fetch_bill": 1}), ScriptedCitizen(NUMBER, YES, YES)
    with pytest.raises(BackendError):
        Engine(fake.client(), io).run("+919999904321", "simulator")
    assert fake.paths().count("/tools/fetch_bill") == 1
    assert fake.ended and fake.bodies(END) == [{"outcome": "abandoned"}]
    assert io.shown[-1][0] == "agent" and "technical problem" in io.shown[-1][2]


def test_a_failed_payment_start_is_not_retried_and_no_bank_result_is_claimed():  # finding 8
    fake, io = FakeBackend(fail={"/tools/start_payment": 1}), ScriptedCitizen(NUMBER, YES, YES)
    with pytest.raises(BackendError):
        Engine(fake.client(), io).run("+919999904321", "simulator")
    assert fake.paths().count("/tools/start_payment") == 1 and STATUS not in fake.paths()
    assert fake.bodies(END) == [{"outcome": "abandoned"}]
    assert not any(word in text_en for _, _, text_en, _ in io.shown for word in ["PENDING", "confirmed", "failed"])


def test_backend_error_after_the_payment_started_says_the_status_is_not_known():  # finding 8
    fake, io = FakeBackend(payment_statuses=["pending"]), ScriptedCitizen(NUMBER, YES, YES)
    fake.fail["/calls/call-1/events"] = 0

    def events_fail_once_the_payment_exists(path, body):
        if path == "/tools/start_payment":
            fake.fail["/calls/call-1/events"] = 10 ** 6

    fake.on_request = events_fail_once_the_payment_exists
    with pytest.raises(BackendError):
        Engine(fake.client(), io).run("+919999904321", "simulator")
    assert fake.paths().count("/tools/start_payment") == 1
    assert fake.ended and fake.outcome == "payment_pending"  # closed; the fake backend derives it from its payment
    spoken = " ".join(text_en for kind, _, text_en, _ in io.shown if kind == "agent")
    assert "technical problem" in spoken and "not known whether the payment went through" in spoken


def test_a_transient_status_read_failure_does_not_stop_the_polling():  # finding 8
    outcome, fake, _, _ = run(NUMBER, YES, YES, payment_statuses=["pending", "confirmed"], fail={STATUS: 2})
    assert outcome == "paid" and fake.paths().count("/tools/start_payment") == 1
    assert "confirmed" in fake.said()[-1]["text_en"]


def test_when_the_status_cannot_be_read_the_agent_says_so_instead_of_a_bank_result():  # finding 8
    outcome, fake, _, sleeps = run(NUMBER, YES, YES, payment_statuses=["confirmed"], fail={STATUS: 10 ** 6})
    assert sum(sleeps) == 60 and fake.paths().count("/tools/start_payment") == 1
    last = fake.said()[-1]
    assert "could not check the payment status" in last["text_en"] and "അറിയാൻ കഴിഞ്ഞില്ല" in last["text"]
    assert not any(word in last["text_en"] for word in ["PENDING", "confirmed", "failed"])
    assert fake.ended and outcome == "payment_pending"  # what the (fake) payment service last reported


def test_ctrl_c_before_the_payment_has_started_ends_as_abandoned_not_pending():  # finding 8
    fake = FakeBackend()
    interrupt_when(fake, lambda path, body: path == "/tools/start_payment")
    outcome = Engine(fake.client(), ScriptedCitizen(NUMBER, YES, YES)).run("+919999904321", "simulator")
    assert outcome == "abandoned" and fake.bodies(END) == [{"outcome": "abandoned"}]


def test_ctrl_c_after_the_bank_result_arrived_ends_with_that_result_not_pending():  # finding 8
    fake = FakeBackend(payment_statuses=["failed"])
    interrupt_when(fake, lambda path, body: "The payment failed" in body.get("text_en", ""))
    outcome = Engine(fake.client(), ScriptedCitizen(NUMBER, YES, YES)).run("+919999904321", "simulator")
    assert outcome == "payment_failed" and fake.bodies(END) == [{"outcome": "payment_failed"}]


def test_the_call_outcome_is_the_one_the_backend_recorded():  # contract, round 1: the payment service decides at /end
    fake, clock = FakeBackend(payment_statuses=["pending"]), FakeClock()

    def bank_confirms_just_before_the_end(path, body):
        if path == END:
            fake.payment["status"] = "confirmed"

    fake.on_request = bank_confirms_just_before_the_end
    outcome = Engine(fake.client(), ScriptedCitizen(NUMBER, YES, YES), sleep=clock.sleep, clock=clock.time).run("+91", "simulator")
    assert "PENDING" in fake.said()[-1]["text_en"]  # voice said only what it had seen
    assert fake.bodies(END) == [{"outcome": "payment_pending"}] and outcome == "paid"


@pytest.mark.parametrize("lines", [(NUMBER,), (NUMBER, YES), (NUMBER, YES, NO), ("ഒരു ആളെ തരൂ",), (NOTHING_DUE, YES)])
def test_no_payment_outcome_is_sent_when_no_payment_exists(lines):
    _, fake, _, _ = run(*lines)
    assert fake.payment is None
    assert fake.bodies(END)[0]["outcome"] in ("abandoned", "handed_off", "nothing_due")


def test_handoff_reads_the_case_number_digit_by_digit_and_promises_no_call_back():  # finding 9
    _, fake, _, _ = run("ഒരു ആളെ തരൂ")
    last = fake.said()[-1]
    assert "നാല്, എട്ട്, രണ്ട്, ഏഴ്" in last["text"] and "4 8 2 7" in last["text_en"]
    assert "CASE-7" not in last["text"] + last["text_en"]
    assert "call you back" not in last["text_en"] and "തിരിച്ചു വിളിക്കും" not in last["text"]
    assert "passing this call" not in last["text_en"] and "കൈമാറുന്നു" not in last["text"]  # nothing is transferred


def test_time_spent_in_status_requests_counts_towards_the_deadline():  # finding 13
    fake, clock = FakeBackend(payment_statuses=["pending"]), FakeClock()

    def slow_status(path, body):
        if path == STATUS:
            clock.now += 5

    fake.on_request = slow_status
    engine = Engine(fake.client(), ScriptedCitizen(NUMBER, YES, YES), poll_interval=2, poll_timeout=12, sleep=clock.sleep, clock=clock.time)
    assert engine.run("+919999904321", "simulator") == "payment_pending"
    assert fake.paths().count(STATUS) == 2 and clock.sleeps == [2] and clock.now == 12


def test_the_last_wait_is_cut_to_the_time_that_remains_and_requests_are_bounded_by_it():  # finding 13
    outcome, fake, _, sleeps = run(NUMBER, YES, YES, poll_timeout=3, payment_statuses=["pending"])
    assert outcome == "payment_pending" and sleeps == [2, 1]
    assert fake.status_timeouts == [3, 1, 1]  # never more than what remains (at least 1 s for the final check)


@pytest.mark.parametrize("interval, timeout", [
    (0, 60), (-1, 60), (float("nan"), 60), (float("inf"), 60), (2, -1), (2, float("inf")), (2, float("nan"))])
def test_invalid_poll_settings_are_rejected_before_a_call_is_created(interval, timeout):  # finding 13
    fake = FakeBackend()
    with pytest.raises(ValueError):
        Engine(fake.client(), ScriptedCitizen(NUMBER), poll_interval=interval, poll_timeout=timeout)
    assert fake.requests == []


@pytest.mark.parametrize("lines", [
    ("എനിക്ക് പെൻഷൻ സർട്ടിഫിക്കറ്റ് വേണം",),
    (NUMBER, "I need a pension certificate"),
    (NUMBER, YES, "റേഷൻ കാർഡ് പുതുക്കണം"),
])
def test_asking_for_another_service_hands_off_as_unsupported_service(lines):  # finding 15
    outcome, fake, io, _ = run(*lines, YES)
    assert outcome == "handed_off" and fake.handoff["reason"] == "unsupported_service"
    assert "/tools/start_payment" not in fake.paths()
    assert citizen_lines(fake, io)[-1] == HEARD_SERVICE
    assert "KSEB" in fake.said()[-1]["text_en"] and "കെ.എസ്.ഇ.ബി." in fake.said()[-1]["text"]
    assert io.lines == [YES]


def test_bill_read_backs_say_simulated_in_malayalam_too():  # finding 17
    _, fake, _, _ = run(NUMBER, YES, YES)
    assert "സിമുലേറ്റഡ്" in next(e for e in fake.said() if "രാജൻ കെ" in e["text"])["text"]
    _, fake, _, _ = run(NOTHING_DUE, YES)
    assert "സിമുലേറ്റഡ്" in fake.said()[-1]["text"]
