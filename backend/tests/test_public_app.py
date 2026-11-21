"""Port 8001 (public_app): the Sarvam Voice Agents phone port. Same handlers as :8000 but only the
call-write/tools routes, each behind `Authorization: Bearer <PHONE_TOOLS_TOKEN>` (except /health)."""
import pytest
from fastapi.testclient import TestClient

from app import create_app

TOKEN = "phone-token-for-tests"
PAYABLE = "1155432100987"  # KSEB-SIM-0001, Rs 640
PHONE = "+91 98765 43210"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def public(db_path):
    with TestClient(create_app(db_path, public=True, phone_token=TOKEN)) as c:
        yield c


@pytest.fixture
def local(db_path):
    with TestClient(create_app(db_path)) as c:
        yield c


def auth(token=TOKEN):
    return {"Authorization": f"Bearer {token}"}


# Every route port 8001 serves except /health (method, path).
PROTECTED = [
    ("post", "/calls"),
    ("post", "/calls/call_x/events"),
    ("post", "/calls/call_x/end"),
    ("post", "/tools/fetch_bill"),
    ("post", "/tools/confirm_amount"),
    ("post", "/tools/start_payment"),
    ("get", "/tools/payment_status/pay_x"),
    ("post", "/tools/handoff"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"},
                                     {"Authorization": f"Bearer {TOKEN}x"},
                                     {"Authorization": TOKEN},
                                     {"Authorization": f"bearer {TOKEN}"}])
def test_missing_or_wrong_token_is_401(public, method, path, headers):
    r = getattr(public, method)(path, headers=headers)
    assert r.status_code == 401 and r.json() == {"error": "unauthorized"}


def test_health_needs_no_token(public):
    assert public.get("/health").json() == {"ok": True}
    assert public.get("/health", headers={"Authorization": "Bearer wrong"}).status_code == 200


def test_refuses_to_start_without_token(db_path, monkeypatch):
    monkeypatch.delenv("PHONE_TOOLS_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="PHONE_TOOLS_TOKEN"):
        create_app(db_path, public=True)
    with pytest.raises(RuntimeError):
        create_app(db_path, public=True, phone_token="")
    monkeypatch.setenv("PHONE_TOOLS_TOKEN", "from-env")
    with TestClient(create_app(db_path, public=True)) as c:
        assert c.get("/health").status_code == 200


# Local-only routes must not exist on the public port, even with the right token.
@pytest.mark.parametrize("method,path", [
    ("get", "/calls"),
    ("get", "/calls/call_x"),
    ("post", "/simulator/payments/pay_x/complete"),
    ("get", "/openapi.json"),
    ("get", "/docs"),
])
def test_local_only_routes_are_404(public, method, path):
    assert getattr(public, method)(path, headers=auth()).status_code == 404


def test_correct_token_runs_the_whole_flow(public):
    r = public.post("/calls", json={"caller_phone": PHONE, "channel": "phone"}, headers=auth())
    assert r.status_code == 201
    cid = r.json()["call_id"]
    assert r.json()["channel"] == "phone" and r.json()["caller_phone_masked"] == "******3210"

    r = public.post(f"/calls/{cid}/events", json={"type": "agent_said", "text": "നമസ്കാരം"}, headers=auth())
    assert r.status_code == 201
    bill = public.post("/tools/fetch_bill", json={"call_id": cid, "consumer_number": PAYABLE,
                                                  "number_confirmed": True}, headers=auth()).json()
    assert bill["bill_id"] == "KSEB-SIM-0001" and bill["simulated"] is True
    r = public.post("/tools/confirm_amount", json={"call_id": cid, "bill_id": bill["bill_id"],
                                                   "citizen_confirmed": True}, headers=auth())
    assert r.json()["amount_confirmed"] is True
    pay = public.post("/tools/start_payment", json={"call_id": cid, "bill_id": bill["bill_id"]},
                      headers=auth()).json()
    assert pay["status"] == "pending" and pay["simulated"] is True
    status = public.get(f"/tools/payment_status/{pay['payment_id']}", headers=auth())
    assert status.json()["status"] == "pending"
    r = public.post("/tools/handoff", json={"call_id": cid, "reason": "citizen_request"}, headers=auth())
    assert r.status_code == 201 and r.json()["status"] == "queued"
    # Pending payment decides the outcome; pending stays pending.
    ended = public.post(f"/calls/{cid}/end", json={"outcome": "abandoned"}, headers=auth()).json()
    assert ended["state"] == "ended" and ended["outcome"] == "payment_pending"


def test_phone_call_is_visible_on_the_local_app(public, local):
    r = public.post("/calls", json={"caller_phone": PHONE, "channel": "phone"}, headers=auth())
    cid = r.json()["call_id"]
    call = local.get(f"/calls/{cid}").json()  # same SQLite file as the public port
    assert call["call_id"] == cid and call["channel"] == "phone" and call["state"] == "greeting"
    assert cid in [c["call_id"] for c in local.get("/calls").json()]
