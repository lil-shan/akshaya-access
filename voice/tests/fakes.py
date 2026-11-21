"""Test doubles: an in-memory backend that follows contracts/tools-api.yaml (served through httpx.MockTransport,
so the real Backend client and its 409 handling are exercised) and a scripted citizen."""
import json
from pathlib import Path

import httpx

from backend import Backend

PAYMENT_OUTCOMES = {"confirmed": "paid", "failed": "payment_failed", "pending": "payment_pending"}
FIXTURES = json.loads((Path(__file__).resolve().parents[2] / "contracts/fixtures/bills.json").read_text())["bills"]


def guard(reason):
    return httpx.Response(409, json={"error": "guard_failed", "reason": reason})


class FakeBackend:
    def __init__(self, payment_statuses=("pending", "pending", "confirmed"), force_guard=None, fail=None):
        self.payment_statuses = list(payment_statuses)  # one per status poll; the last one repeats
        self.force_guard = force_guard or {}  # path -> guard reason to return instead of the normal reply
        self.fail = dict(fail or {})  # path -> how many requests to answer with HTTP 500
        self.on_request = None  # optional hook(path, body): advance a fake clock, interrupt, ...
        self.status_timeouts = []  # read timeout of each payment status request
        self.requests = []  # (method, path, body)
        self.events = []
        self.bill = self.payment = self.handoff = self.outcome = None
        self.ended = False

    def client(self):
        return Backend(client=httpx.Client(transport=httpx.MockTransport(self._handle), base_url="http://backend.test"))

    def _handle(self, request):
        path, body = request.url.path, json.loads(request.content or b"{}")
        self.requests.append((request.method, path, body))
        if self.on_request:
            self.on_request(path, body)
        if self.fail.get(path, 0) > 0:
            self.fail[path] -= 1
            return httpx.Response(500, json={"error": "internal"})
        if path in self.force_guard:
            return guard(self.force_guard[path])
        if path == "/calls":
            return httpx.Response(201, json={"call_id": "call-1", "state": "greeting", "events": []})
        if path == "/calls/call-1/events":
            if self.ended:
                return guard("call_ended")
            self.events.append(body)
            return httpx.Response(201, json={**body, "seq": len(self.events), "at": "2026-11-21T10:00:00Z"})
        if path == "/calls/call-1/end":
            outcome = body.get("outcome")
            if self.payment:  # contract, round 1: the payment service decides, whatever the client sent
                outcome = PAYMENT_OUTCOMES[self.payment["status"]]
            elif outcome in PAYMENT_OUTCOMES.values():
                return guard("payment_outcome_without_payment")
            self.ended, self.outcome = True, outcome
            return httpx.Response(200, json={"call_id": "call-1", "state": "ended", "outcome": self.outcome})
        if path == "/tools/fetch_bill":
            if body["number_confirmed"] is not True:
                return guard("number_not_confirmed")
            found = [b for b in FIXTURES if b["consumer_number"] == body["consumer_number"]]
            if not found:
                return httpx.Response(404, json={"error": "not_found", "reason": "bill_not_found"})
            self.bill = {k: v for k, v in found[0].items() if not k.startswith("_")}
            self.bill |= {"biller": "KSEB", "amount_confirmed": False, "simulated": True}
            return httpx.Response(200, json=self.bill)
        if path == "/tools/confirm_amount":
            self.bill["amount_confirmed"] = body["citizen_confirmed"]
            return httpx.Response(200, json=self.bill)
        if path == "/tools/start_payment":
            if not self.bill["amount_confirmed"]:
                return guard("amount_not_confirmed")
            if self.bill["amount_inr"] == 0:
                return guard("nothing_due")
            if self.payment:
                return guard("payment_already_started")
            self.payment = {"payment_id": "pay-1", "bill_id": self.bill["bill_id"], "method": "UPI_123PAY",
                            "amount_inr": self.bill["amount_inr"], "status": "pending", "reference": None, "simulated": True}
            return httpx.Response(201, json=self.payment)
        if path == "/tools/payment_status/pay-1":
            self.status_timeouts.append(request.extensions["timeout"]["read"])
            status = self.payment_statuses.pop(0) if len(self.payment_statuses) > 1 else self.payment_statuses[0]
            self.payment |= {"status": status, "reference": "SIMREF123456" if status == "confirmed" else None}
            return httpx.Response(200, json=self.payment)
        if path == "/tools/handoff":
            self.handoff = {"case_id": "CASE-7", "case_number": "4827", "call_id": body["call_id"], "reason": body["reason"],
                            "note": body.get("note"), "status": "queued"}
            return httpx.Response(201, json=self.handoff)
        return httpx.Response(404, json={"error": "not_found"})

    def paths(self):
        return [path for _, path, _ in self.requests]

    def bodies(self, path):
        return [body for _, p, body in self.requests if p == path]

    def said(self, kind="agent_said"):
        return [e for e in self.events if e["type"] == kind]

    def states(self):
        return [e["text"] for e in self.events if e["type"] == "state"]


class FakeClock:
    """A monotonic clock that only moves when the engine sleeps (or a test advances it)."""

    def __init__(self):
        self.now, self.sleeps = 0.0, []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class ScriptedCitizen:
    """IO for the engine: says the given lines in order, then hangs up.
    Agent lines whose English text contains one of `unheard` fail to play (show() returns False)."""

    def __init__(self, *lines, unheard=()):
        self.lines = list(lines)
        self.unheard = unheard
        self.shown = []

    def listen(self):
        return self.lines.pop(0) if self.lines else None

    def show(self, kind, text, text_en="", both=False):
        self.shown.append((kind, text, text_en, both))
        return not (kind == "agent" and any(part in text_en for part in self.unheard))
