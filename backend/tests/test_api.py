import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import create_app

PAYABLE = "1155432100987"  # KSEB-SIM-0001, Rs 640
NOTHING_DUE = "1150000000000"  # KSEB-SIM-0003, Rs 0
PHONE = "+91 98765 43210"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def client(db_path):
    with TestClient(create_app(db_path)) as c:
        yield c


def new_call(client):
    r = client.post("/calls", json={"caller_phone": PHONE, "channel": "simulator"})
    assert r.status_code == 201, r.text
    return r.json()["call_id"]


def fetch(client, call_id, number=PAYABLE, confirmed=True):
    return client.post("/tools/fetch_bill", json={"call_id": call_id, "consumer_number": number,
                                                  "number_confirmed": confirmed})


def confirm(client, call_id, bill_id, yes=True):
    return client.post("/tools/confirm_amount", json={"call_id": call_id, "bill_id": bill_id, "citizen_confirmed": yes})


def start(client, call_id, bill_id):
    return client.post("/tools/start_payment", json={"call_id": call_id, "bill_id": bill_id})


def assert_guard(r, reason):
    assert r.status_code == 409, r.text
    assert r.json() == {"error": "guard_failed", "reason": reason}


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_happy_path(client):
    cid = new_call(client)
    assert client.get(f"/calls/{cid}").json()["state"] == "greeting"
    assert client.post(f"/calls/{cid}/events", json={"type": "agent_said", "text": "നമസ്കാരം", "text_en": "Hello"}).status_code == 201
    client.post(f"/calls/{cid}/events", json={"type": "state", "text": "fetching_bill"})

    bill = fetch(client, cid).json()
    assert bill == {"bill_id": "KSEB-SIM-0001", "biller": "KSEB", "consumer_number": PAYABLE, "customer_name": "രാജൻ കെ",
                    "customer_name_en": "Rajan K", "amount_inr": 640, "due_date": "2027-02-12",
                    "amount_confirmed": False, "simulated": True}
    assert confirm(client, cid, bill["bill_id"]).json()["amount_confirmed"] is True

    r = start(client, cid, bill["bill_id"])
    assert r.status_code == 201
    pay = r.json()
    assert pay["status"] == "pending" and pay["method"] == "UPI_123PAY" and pay["amount_inr"] == 640
    assert pay["simulated"] is True and pay["reference"] is None
    assert client.get(f"/tools/payment_status/{pay['payment_id']}").json()["status"] == "pending"

    r = client.post(f"/simulator/payments/{pay['payment_id']}/complete", json={"outcome": "confirmed"})
    assert r.status_code == 200
    status = client.get(f"/tools/payment_status/{pay['payment_id']}").json()
    assert status["status"] == "confirmed" and status["reference"] == "SIM123PAY-000001"

    ended = client.post(f"/calls/{cid}/end", json={"outcome": "paid"}).json()
    assert ended["state"] == "ended" and ended["outcome"] == "paid" and ended["ended_at"]
    call = client.get(f"/calls/{cid}").json()
    assert [e["seq"] for e in call["events"]] == [1, 2]
    assert call["events"][0]["text_en"] == "Hello" and "text_en" not in call["events"][1]
    assert call["bill"]["amount_confirmed"] is True
    assert call["payment"]["status"] == "confirmed" and call["handoff"] is None


def test_caller_phone_masked_everywhere(client, db_path):
    cid = new_call(client)
    assert client.get(f"/calls/{cid}").json()["caller_phone_masked"] == "******3210"
    assert client.get("/calls").json()[0]["caller_phone_masked"] == "******3210"
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT caller_phone_masked FROM calls").fetchall() == [("******3210",)]
    raw = db_path.read_bytes()
    assert b"9876543210" not in raw and b"98765 43210" not in raw


def test_fetch_bill_requires_confirmed_number(client):
    assert_guard(fetch(client, new_call(client), confirmed=False), "number_not_confirmed")


def test_number_confirmed_must_be_a_real_boolean(client):
    assert fetch(client, new_call(client), confirmed="yes").status_code == 422


def test_fetch_bill_validates_and_404s(client):
    cid = new_call(client)
    assert fetch(client, cid, number="115543210098").status_code == 422
    r = fetch(client, cid, number="9999999999999")
    assert r.status_code == 404 and r.json()["error"] == "not_found"


@pytest.mark.parametrize("yes", [None, False])
def test_start_payment_requires_confirmed_amount(client, yes):
    cid = new_call(client)
    bill_id = fetch(client, cid).json()["bill_id"]
    if yes is not None:
        confirm(client, cid, bill_id, yes)
    assert_guard(start(client, cid, bill_id), "amount_not_confirmed")


def test_start_payment_nothing_due(client):
    cid = new_call(client)
    bill_id = fetch(client, cid, number=NOTHING_DUE).json()["bill_id"]
    confirm(client, cid, bill_id)
    assert_guard(start(client, cid, bill_id), "nothing_due")
    assert client.get(f"/calls/{cid}").json()["payment"] is None


def test_start_payment_twice(client):
    cid = new_call(client)
    bill_id = fetch(client, cid).json()["bill_id"]
    confirm(client, cid, bill_id)
    assert start(client, cid, bill_id).status_code == 201
    assert_guard(start(client, cid, bill_id), "payment_already_started")


def test_bill_must_belong_to_call(client):
    a, b = new_call(client), new_call(client)
    bill_id = fetch(client, a).json()["bill_id"]
    confirm(client, a, bill_id)
    assert_guard(confirm(client, b, bill_id), "bill_not_found")
    assert_guard(start(client, b, bill_id), "bill_not_found")
    assert_guard(start(client, a, "KSEB-SIM-0002"), "bill_not_found")  # real bill, never fetched on this call


def paying_call(client, number=PAYABLE):
    """A call with a pending payment. Returns (call_id, payment_id)."""
    cid = new_call(client)
    bill_id = fetch(client, cid, number).json()["bill_id"]
    assert confirm(client, cid, bill_id).status_code == 200
    r = start(client, cid, bill_id)
    assert r.status_code == 201, r.text
    return cid, r.json()["payment_id"]


def complete(client, pid, outcome):
    assert client.post(f"/simulator/payments/{pid}/complete", json={"outcome": outcome}).status_code == 200


def test_pending_payment_blocks_same_bill_in_another_call(client, db_path):
    paying_call(client)
    cid = new_call(client)
    bill_id = fetch(client, cid).json()["bill_id"]
    confirm(client, cid, bill_id)
    assert_guard(start(client, cid, bill_id), "payment_already_started")
    assert client.get(f"/calls/{cid}").json()["payment"] is None
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM payments").fetchone() == (1,)


@pytest.mark.parametrize("first", ["confirmed", "failed"])
def test_bill_can_be_replayed_after_a_final_result(client, first):
    _, pid = paying_call(client)
    complete(client, pid, first)
    _, pid2 = paying_call(client)
    assert pid2 != pid
    assert client.get(f"/tools/payment_status/{pid2}").json()["status"] == "pending"


def test_one_payment_per_call_even_for_another_bill(client):
    cid, pid = paying_call(client)
    complete(client, pid, "failed")
    assert_guard(fetch(client, cid, "1156789012345"), "payment_already_started")  # payable bill is locked
    assert_guard(start(client, cid, "KSEB-SIM-0001"), "payment_already_started")
    assert client.get(f"/calls/{cid}").json()["bill"]["bill_id"] == "KSEB-SIM-0001"


def test_confirmation_is_tied_to_the_current_bill(client):
    cid = new_call(client)
    a = fetch(client, cid).json()["bill_id"]
    assert confirm(client, cid, a).json()["amount_confirmed"] is True
    b = fetch(client, cid, "1156789012345").json()
    assert b["bill_id"] == "KSEB-SIM-0002" and b["amount_confirmed"] is False
    assert_guard(start(client, cid, a), "bill_not_found")  # stale request for the old bill
    assert_guard(confirm(client, cid, a), "bill_not_found")
    assert_guard(start(client, cid, b["bill_id"]), "amount_not_confirmed")
    assert client.get(f"/calls/{cid}").json()["bill"]["bill_id"] == b["bill_id"]
    # Re-selecting A does not resurrect its old confirmation.
    again = fetch(client, cid).json()
    assert again["bill_id"] == a and again["amount_confirmed"] is False
    assert_guard(start(client, cid, a), "amount_not_confirmed")
    assert confirm(client, cid, a).status_code == 200
    r = start(client, cid, a)
    assert r.status_code == 201 and r.json()["bill_id"] == a and r.json()["amount_inr"] == 640


def test_unknown_number_clears_the_current_bill(client):
    cid = new_call(client)
    a = fetch(client, cid).json()["bill_id"]
    confirm(client, cid, a)
    r = fetch(client, cid, "9999999999999")
    assert r.status_code == 404 and r.json() == {"error": "not_found", "reason": "no_bill_for_consumer_number"}
    assert client.get(f"/calls/{cid}").json()["bill"] is None
    assert_guard(start(client, cid, a), "bill_not_found")


@pytest.mark.parametrize("path,body", [
    ("/calls/{cid}/events", {"type": "agent_said", "text": "hi"}),
    ("/tools/fetch_bill", {"call_id": "{cid}", "consumer_number": PAYABLE, "number_confirmed": True}),
    ("/tools/confirm_amount", {"call_id": "{cid}", "bill_id": "KSEB-SIM-0001", "citizen_confirmed": True}),
    ("/tools/start_payment", {"call_id": "{cid}", "bill_id": "KSEB-SIM-0001"}),
    ("/tools/handoff", {"call_id": "{cid}", "reason": "citizen_request"}),
])
def test_ended_call_blocks_tools_and_events(client, path, body):
    cid = new_call(client)
    bill_id = fetch(client, cid).json()["bill_id"]
    confirm(client, cid, bill_id)
    client.post(f"/calls/{cid}/end", json={"outcome": "abandoned"})
    body = {k: v.replace("{cid}", cid) if isinstance(v, str) else v for k, v in body.items()}
    assert_guard(client.post(path.replace("{cid}", cid), json=body), "call_ended")


def test_end_twice_keeps_first_outcome(client):
    cid = new_call(client)
    first = client.post(f"/calls/{cid}/end", json={"outcome": "nothing_due"}).json()
    second = client.post(f"/calls/{cid}/end", json={"outcome": "abandoned"}).json()
    assert second["outcome"] == "nothing_due" and second["ended_at"] == first["ended_at"]
    assert client.post(f"/calls/{new_call(client)}/end").status_code == 200  # body is optional
    assert client.post(f"/calls/{new_call(client)}/end", json={"outcome": None}).status_code == 200


@pytest.mark.parametrize("status,expected", [("pending", "payment_pending"), ("failed", "payment_failed"),
                                             ("confirmed", "paid")])
@pytest.mark.parametrize("sent", ["paid", "payment_failed", "payment_pending", "abandoned", "handed_off", None])
def test_outcome_comes_from_the_payment(client, db_path, status, expected, sent):
    cid, pid = paying_call(client)
    if status != "pending":
        complete(client, pid, status)
    r = client.post(f"/calls/{cid}/end", json={"outcome": sent})
    assert r.status_code == 200 and r.json()["outcome"] == expected
    assert client.get(f"/calls/{cid}").json()["outcome"] == expected
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT outcome FROM calls WHERE call_id = ?", (cid,)).fetchone() == (expected,)


@pytest.mark.parametrize("sent", ["paid", "payment_failed", "payment_pending"])
def test_payment_outcome_without_payment_is_rejected(client, sent):
    cid = new_call(client)
    assert_guard(client.post(f"/calls/{cid}/end", json={"outcome": sent}), "payment_outcome_without_payment")
    call = client.get(f"/calls/{cid}").json()
    assert call["ended_at"] is None and call["outcome"] is None and call["state"] == "greeting"


@pytest.mark.parametrize("sent", ["nothing_due", "handed_off", "abandoned", None])
def test_other_outcomes_without_payment_are_taken_as_sent(client, sent):
    cid = new_call(client)
    assert client.post(f"/calls/{cid}/end", json={"outcome": sent}).json()["outcome"] == sent


def test_state_event_sets_state_and_rejects_unknown(client):
    cid = new_call(client)
    assert client.post(f"/calls/{cid}/events", json={"type": "state", "text": "confirming_number"}).status_code == 201
    assert client.get(f"/calls/{cid}").json()["state"] == "confirming_number"
    r = client.post(f"/calls/{cid}/events", json={"type": "state", "text": "flying"})
    assert r.status_code == 422 and r.json() == {"error": "invalid_request", "fields": ["text"]}
    assert client.get(f"/calls/{cid}").json()["state"] == "confirming_number"


@pytest.mark.parametrize("state", ["done", "handed_off"])
def test_intermediate_states_do_not_end_the_call(client, state):
    cid = new_call(client)
    client.post(f"/calls/{cid}/events", json={"type": "state", "text": state})
    call = client.get(f"/calls/{cid}").json()
    assert call["state"] == state and call["ended_at"] is None


def test_state_ended_behaves_like_end(client):
    cid = new_call(client)
    r = client.post(f"/calls/{cid}/events", json={"type": "state", "text": "ended"})
    assert r.status_code == 201 and r.json()["text"] == "ended"
    call = client.get(f"/calls/{cid}").json()
    assert call["state"] == "ended" and call["ended_at"] and call["outcome"] == "abandoned"
    assert cid not in [c["call_id"] for c in client.get("/calls?active=true").json()]
    assert_guard(client.post(f"/calls/{cid}/events", json={"type": "agent_said", "text": "x"}), "call_ended")
    assert_guard(fetch(client, cid), "call_ended")
    assert_guard(client.post("/tools/handoff", json={"call_id": cid, "reason": "other"}), "call_ended")
    again = client.post(f"/calls/{cid}/end", json={"outcome": "nothing_due"}).json()
    assert again["outcome"] == "abandoned" and again["ended_at"] == call["ended_at"]


def test_state_ended_with_pending_payment_reports_pending(client):
    cid, _ = paying_call(client)
    client.post(f"/calls/{cid}/events", json={"type": "state", "text": "ended"})
    assert client.get(f"/calls/{cid}").json()["outcome"] == "payment_pending"


SENTINEL = "98765012345"  # a harmless stand-in for a sensitive value


def server_logs(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records if r.name != "httpx")  # httpx = the test client itself


@pytest.mark.parametrize("path,body,fields", [
    ("/tools/start_payment", {"call_id": "x", "bill_id": "y", "upi_pin": SENTINEL}, ["unknown_field"]),
    ("/tools/start_payment", {"call_id": "x", "bill_id": "y", "amount_inr": 1}, ["unknown_field"]),
    ("/tools/fetch_bill", {"call_id": "x", "consumer_number": PAYABLE, "number_confirmed": True, "otp": SENTINEL},
     ["unknown_field"]),
    ("/calls", {"caller_phone": PHONE, "channel": "phone", "aadhaar": SENTINEL}, ["unknown_field"]),
    ("/calls", {"caller_phone": PHONE, "channel": "phone", f"x{SENTINEL}": 1}, ["unknown_field"]),
    ("/tools/handoff", {"call_id": "x", "reason": "other", "card_number": SENTINEL}, ["unknown_field"]),
    ("/calls", {"caller_phone": f"+91{SENTINEL}"}, ["channel"]),  # missing field: default 422 echoes the whole object
    ("/calls", {"caller_phone": f"+91{SENTINEL}", "channel": f"fax{SENTINEL}"}, ["channel"]),
    ("/calls", {"caller_phone": PHONE, "channel": "phone", "language": f"ml {SENTINEL}"}, ["language"]),
    ("/tools/fetch_bill", {"call_id": "x", "consumer_number": f"{SENTINEL}xx", "number_confirmed": True},
     ["consumer_number"]),
    ("/tools/fetch_bill", {"call_id": "x", "consumer_number": PAYABLE, "number_confirmed": SENTINEL},
     ["number_confirmed"]),
    ("/tools/handoff", {"call_id": "x", "reason": SENTINEL, "note": SENTINEL * 50}, ["reason", "note"]),
    ("/calls/x/events", {"type": "state", "text": SENTINEL}, ["text"]),
    ("/calls/x/end", {"outcome": SENTINEL}, ["outcome"]),
    ("/simulator/payments/x/complete", {"outcome": SENTINEL}, ["outcome"]),
])
def test_invalid_requests_never_echo_submitted_values(client, caplog, path, body, fields):
    caplog.set_level("DEBUG")
    r = client.post(path, json=body)
    assert r.status_code == 422
    assert r.json() == {"error": "invalid_request", "fields": fields}
    assert SENTINEL not in r.text and SENTINEL not in server_logs(caplog)


def test_malformed_json_and_bad_query_are_safe(client, caplog):
    caplog.set_level("DEBUG")
    r = client.post("/calls", content=f'{{"caller_phone": "{SENTINEL}', headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json() == {"error": "invalid_request", "fields": ["body"]}
    r2 = client.get(f"/calls?active={SENTINEL}")
    assert r2.status_code == 422 and r2.json() == {"error": "invalid_request", "fields": ["active"]}
    assert SENTINEL not in r.text + r2.text + server_logs(caplog)


def test_optional_fields_accept_null(client):
    r = client.post("/calls", json={"caller_phone": PHONE, "channel": "audio", "language": None})
    assert r.status_code == 201 and r.json()["language"] == "ml"
    cid = r.json()["call_id"]
    assert client.post("/calls", json={"caller_phone": PHONE, "channel": "audio", "language": "en-IN"}).status_code == 201
    assert client.post(f"/calls/{cid}/events", json={"type": "agent_said", "text": "hi", "text_en": None}).status_code == 201
    r = client.post("/tools/fetch_bill", json={"call_id": cid, "biller": None, "consumer_number": PAYABLE,
                                               "number_confirmed": True})
    assert r.status_code == 200
    assert client.post("/tools/handoff", json={"call_id": cid, "reason": "other", "note": None}).json()["note"] is None


REDACTION_CASES = [
    ("my pin is 4826", "my pin is [REDACTED]"),
    ("otp 482913", "otp [REDACTED]"),
    ("otp 482 913", "otp [REDACTED]"),
    ("call me on 98765 43210", "call me on [REDACTED]"),
    ("phone 9876-543-210.", "phone [REDACTED]."),
    ("aadhaar 1234 5678 9012, card 4111-1111-1111-1111", "aadhaar [REDACTED], card [REDACTED]"),
    ("1 2 3 4", "[REDACTED]"),
    ("pin ൪൮൨൬", "pin [REDACTED]"),  # Malayalam digits
    (f"consumer number {PAYABLE}", f"consumer number {PAYABLE}"),  # the legitimate read-back is kept
    (f"consumer number {PAYABLE} pin 4826", f"consumer number {PAYABLE} pin [REDACTED]"),
    (f"{PAYABLE} 4826", "[REDACTED]"),  # 13 digits plus more is not a consumer number
    ("1155 4321 00987", "[REDACTED]"),  # only an unseparated 13-digit number is exempt
    ("12345678901234", "[REDACTED]"),
    ("yes, 640 rupees", "yes, 640 rupees"),
]


@pytest.mark.parametrize("said,stored", REDACTION_CASES)
def test_citizen_text_is_redacted_before_storage(client, db_path, said, stored):
    cid = new_call(client)
    r = client.post(f"/calls/{cid}/events", json={"type": "citizen_said", "text": said, "text_en": said})
    assert r.status_code == 201 and r.json()["text"] == stored and r.json()["text_en"] == stored
    assert client.get(f"/calls/{cid}").json()["events"][0]["text"] == stored
    assert client.get("/calls").json()[0]["events"][0]["text_en"] == stored
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT text, text_en FROM events").fetchall() == [(stored, stored)]


@pytest.mark.parametrize("said,stored", REDACTION_CASES)
def test_handoff_note_is_redacted_before_storage(client, db_path, said, stored):
    cid = new_call(client)
    r = client.post("/tools/handoff", json={"call_id": cid, "reason": "other", "note": said})
    assert r.status_code == 201 and r.json()["note"] == stored
    assert client.get(f"/calls/{cid}").json()["handoff"]["note"] == stored
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT note FROM handoffs").fetchall() == [(stored,)]


def test_secrets_never_reach_the_db_file(client, db_path):
    cid = new_call(client)
    client.post(f"/calls/{cid}/events", json={"type": "citizen_said", "text": "pin 4826 otp 913377 ph 9876543210"})
    client.post("/tools/handoff", json={"call_id": cid, "reason": "other", "note": "aadhaar 1234-5678-9012"})
    raw = db_path.read_bytes()
    # (the 4-digit PIN is checked per column above; 4 digits could occur by chance inside a random id)
    for secret in (b"913377", b"9876543210", b"1234-5678-9012", b"123456789012"):
        assert secret not in raw


def test_agent_lines_are_stored_as_sent(client):
    cid = new_call(client)
    text = "Case number 4821. Amount 1285 rupees."
    assert client.post(f"/calls/{cid}/events", json={"type": "agent_said", "text": text, "text_en": text}).json()["text"] == text


def test_db_has_no_sensitive_columns(client, db_path):
    with sqlite3.connect(db_path) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        cols = [c[1].lower() for t in tables for c in conn.execute(f"PRAGMA table_info({t})")]
    assert not [c for c in cols if any(w in c for w in ("otp", "pin", "aadhaar", "card", "cvv"))]
    assert "caller_phone" not in cols  # only caller_phone_masked


def test_simulator_complete_rules(client):
    cid = new_call(client)
    bill_id = fetch(client, cid).json()["bill_id"]
    confirm(client, cid, bill_id)
    pid = start(client, cid, bill_id).json()["payment_id"]
    failed = client.post(f"/simulator/payments/{pid}/complete", json={"outcome": "failed"}).json()
    assert failed["status"] == "failed" and failed["reference"] is None
    r = client.post(f"/simulator/payments/{pid}/complete", json={"outcome": "confirmed"})
    assert r.status_code == 409 and r.json()["error"] == "payment_not_pending"
    assert client.get(f"/tools/payment_status/{pid}").json()["status"] == "failed"
    assert client.post("/simulator/payments/nope/complete", json={"outcome": "confirmed"}).status_code == 404
    assert client.get("/tools/payment_status/nope").status_code == 404


def test_handoff_queued_on_call(client):
    cid = new_call(client)
    r = client.post("/tools/handoff", json={"call_id": cid, "reason": "number_unclear"})
    assert r.status_code == 201
    case = r.json()
    assert case["status"] == "queued" and case["call_id"] == cid and case["note"] is None
    assert re.fullmatch(r"[0-9]{4}", case["case_number"])
    assert client.get(f"/calls/{cid}").json()["handoff"] == case


def test_case_numbers_unique_among_queued(client, monkeypatch):
    import app as app_module
    picks = iter(["1234", "1234", "5678"])
    # A stand-in for secrets.choice that tries 1234 twice: the second pick must not reuse a queued number.
    monkeypatch.setattr(app_module.secrets, "choice", lambda free: next(p for p in picks if p in free))
    numbers = [client.post("/tools/handoff", json={"call_id": new_call(client), "reason": "other"}).json()["case_number"]
               for _ in range(2)]
    assert numbers == ["1234", "5678"]


def test_list_calls_newest_first_and_active_filter(client):
    a, b = new_call(client), new_call(client)
    client.post(f"/calls/{a}/end", json={"outcome": "abandoned"})
    assert [c["call_id"] for c in client.get("/calls").json()] == [b, a]
    assert [c["call_id"] for c in client.get("/calls?active=true").json()] == [b]


def test_unknown_call_404(client):
    assert client.get("/calls/nope").status_code == 404
    assert client.post("/calls/nope/events", json={"type": "agent_said", "text": "x"}).status_code == 404
    assert fetch(client, "nope").status_code == 404


def test_cors_allows_frontend(client):
    r = client.options("/calls", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
