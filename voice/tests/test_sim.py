import builtins
from pathlib import Path

import pytest

import sim
from fakes import FakeBackend

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.mark.parametrize("script, outcome, handoff_reason", [
    ("happy_path.txt", "paid", None),
    ("nothing_due.txt", "nothing_due", None),
    ("handoff.txt", "handed_off", "citizen_request"),
    ("handoff_number_unclear.txt", "handed_off", "number_unclear"),
])
def test_demo_scripts_run_to_their_outcome(script, outcome, handoff_reason, capsys):
    fake = FakeBackend(payment_statuses=["confirmed"])
    assert sim.main(["--script", str(SCRIPTS / script)], backend=fake.client()) == 0
    assert fake.outcome == outcome
    assert (fake.handoff or {}).get("reason") == handoff_reason
    assert fake.bodies("/calls")[0]["channel"] == "simulator"
    assert f"outcome={outcome}" in capsys.readouterr().out


def test_script_mode_prints_the_whole_conversation(capsys):
    fake = FakeBackend(payment_statuses=["confirmed"])
    sim.main(["--script", str(SCRIPTS / "happy_path.txt")], backend=fake.client())
    out = capsys.readouterr().out
    for event in fake.events:
        assert event["text"] in out
        assert event.get("text_en", "") in out
    assert out.index("I am an AI assistant") < out.index("consumer number 1155432100987") < out.index("SIMREF123456")
    assert "pay-1" in out  # so the payment can be completed from the command line


def test_interactive_mode_reads_citizen_lines_from_the_keyboard(monkeypatch, capsys):
    typed = iter(["1150000000000", "yes"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(typed))
    fake = FakeBackend()
    assert sim.main([], backend=fake.client()) == 0
    assert fake.outcome == "nothing_due"


def test_interactive_end_of_input_hangs_up(monkeypatch):
    def end_of_input(prompt=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", end_of_input)
    fake = FakeBackend()
    assert sim.main([], backend=fake.client()) == 0
    assert fake.outcome == "abandoned"


def test_poll_interval_and_timeout_come_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("PAYMENT_POLL_INTERVAL_S", "0.25")
    monkeypatch.setenv("PAYMENT_POLL_TIMEOUT_S", "0.5")
    fake = FakeBackend(payment_statuses=["pending"])
    sim.main(["--script", str(SCRIPTS / "happy_path.txt")], backend=fake.client())
    assert fake.outcome == "payment_pending"
    assert fake.paths().count("/tools/payment_status/pay-1") == 3


def test_audio_mode_without_key_exits_with_a_clear_message_before_any_call(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    fake = FakeBackend()
    with pytest.raises(SystemExit) as exit_info:
        sim.main(["--audio"], backend=fake.client())
    assert "SARVAM_API_KEY" in str(exit_info.value)
    assert fake.requests == []


def test_backend_failure_is_reported_and_returns_nonzero(capsys):
    fake = FakeBackend(force_guard={"/tools/handoff": "call_ended"})
    assert sim.main(["--script", str(SCRIPTS / "handoff.txt")], backend=fake.client()) == 1
    assert "call_ended" in capsys.readouterr().err
