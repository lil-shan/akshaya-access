"""Akshaya-Access Tools API (ideathon prototype). Implements contracts/tools-api.yaml.
Bill fetch (KSEB) and payment (UPI 123PAY) are SIMULATED adapters, see adapters.py."""
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, get_args

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationInfo, field_validator

from adapters import BillerAdapter, PaymentAdapter, SimulatedKSEB, SimulatedUPI123Pay

CallState = Literal["greeting", "collecting_number", "confirming_number", "fetching_bill", "confirming_amount",
                    "paying", "done", "handed_off", "ended"]
Outcome = Literal["paid", "payment_failed", "payment_pending", "nothing_due", "handed_off", "abandoned"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
  call_id TEXT PRIMARY KEY, caller_phone_masked TEXT NOT NULL, channel TEXT NOT NULL, language TEXT NOT NULL,
  state TEXT NOT NULL, outcome TEXT, started_at TEXT NOT NULL, ended_at TEXT, bill_id TEXT);
CREATE TABLE IF NOT EXISTS events (
  call_id TEXT NOT NULL, seq INTEGER NOT NULL, type TEXT NOT NULL, text TEXT NOT NULL, text_en TEXT, at TEXT NOT NULL,
  PRIMARY KEY (call_id, seq));
CREATE TABLE IF NOT EXISTS bills (
  call_id TEXT NOT NULL, bill_id TEXT NOT NULL, consumer_number TEXT NOT NULL, customer_name TEXT NOT NULL,
  customer_name_en TEXT, amount_inr INTEGER NOT NULL, due_date TEXT, amount_confirmed INTEGER NOT NULL DEFAULT 0,
  simulated INTEGER NOT NULL, PRIMARY KEY (call_id, bill_id));
CREATE TABLE IF NOT EXISTS payments (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, payment_id TEXT NOT NULL UNIQUE, call_id TEXT NOT NULL, bill_id TEXT NOT NULL,
  amount_inr INTEGER NOT NULL, status TEXT NOT NULL, reference TEXT, simulated INTEGER NOT NULL,
  UNIQUE (call_id, bill_id));
CREATE TABLE IF NOT EXISTS handoffs (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL UNIQUE, case_number TEXT NOT NULL, call_id TEXT NOT NULL,
  reason TEXT NOT NULL, note TEXT, status TEXT NOT NULL);
"""

# Any run of 4+ digits (PIN, OTP, phone, Aadhaar, card...), even when split by spaces/dashes/dots/commas, is redacted
# from citizen text before it is stored. Only an exact, unseparated 13-digit consumer number is kept.
DIGIT_RUN = re.compile(r"\d(?:[\s,.\-]*\d){3,}")
PAYMENT_OUTCOMES = {"confirmed": "paid", "failed": "payment_failed", "pending": "payment_pending"}


class GuardFailed(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class NotFound(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class In(BaseModel):
    # Unknown fields are rejected, so there is nowhere to send an OTP, UPI PIN, Aadhaar or card number.
    model_config = ConfigDict(extra="forbid")


class CallIn(In):
    caller_phone: str
    channel: Literal["phone", "simulator", "audio"]
    language: str | None = Field("ml", pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")  # a language tag, e.g. ml, ml-IN


class EventIn(In):
    type: Literal["agent_said", "citizen_said", "state"]
    text: str
    text_en: str | None = None

    @field_validator("text")
    @classmethod
    def state_must_be_known(cls, text: str, info: ValidationInfo):
        if info.data.get("type") == "state" and text not in get_args(CallState):
            raise ValueError("unknown state")
        return text


class EndIn(In):
    outcome: Outcome | None = None


class FetchBillIn(In):
    call_id: str
    biller: Literal["KSEB"] | None = "KSEB"
    consumer_number: str = Field(pattern=r"^[0-9]{13}$")
    number_confirmed: StrictBool


class ConfirmAmountIn(In):
    call_id: str
    bill_id: str
    citizen_confirmed: StrictBool


class StartPaymentIn(In):
    call_id: str
    bill_id: str


class HandoffIn(In):
    call_id: str
    reason: Literal["number_unclear", "citizen_request", "unsupported_service", "payment_problem", "other"]
    note: str | None = Field(None, max_length=500)


class CompleteIn(In):
    outcome: Literal["confirmed", "failed"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def mask_phone(raw: str) -> str:
    return "******" + re.sub(r"\D", "", raw)[-4:]


def redact(text: str | None) -> str | None:
    if not text:
        return text
    return DIGIT_RUN.sub(lambda m: m[0] if len(m[0]) == 13 and m[0].isdigit() else "[REDACTED]", text)


def drop_none(d: dict, *keys: str) -> dict:
    return {k: v for k, v in d.items() if not (k in keys and v is None)}


def bill_json(b) -> dict:
    return drop_none({"bill_id": b["bill_id"], "biller": "KSEB", "consumer_number": b["consumer_number"],
                      "customer_name": b["customer_name"], "customer_name_en": b["customer_name_en"],
                      "amount_inr": b["amount_inr"], "due_date": b["due_date"],
                      "amount_confirmed": bool(b["amount_confirmed"]), "simulated": bool(b["simulated"])},
                     "customer_name_en")


def payment_json(p) -> dict:
    return {"payment_id": p["payment_id"], "bill_id": p["bill_id"], "method": "UPI_123PAY", "amount_inr": p["amount_inr"],
            "status": p["status"], "reference": p["reference"], "simulated": bool(p["simulated"])}


def handoff_json(h) -> dict:
    return {"case_id": h["case_id"], "case_number": h["case_number"], "call_id": h["call_id"], "reason": h["reason"],
            "note": h["note"], "status": h["status"]}


def event_json(e) -> dict:
    return drop_none({"seq": e["seq"], "at": e["at"], "type": e["type"], "text": e["text"], "text_en": e["text_en"]},
                     "text_en")


def create_app(db_path: str | Path | None = None, biller: BillerAdapter | None = None,
               payments: PaymentAdapter | None = None, *, public: bool = False,
               phone_token: str | None = None) -> FastAPI:
    db_path = str(db_path or os.environ.get("BACKEND_DB_PATH") or Path(__file__).parent / "data.db")
    biller = biller or SimulatedKSEB()
    payments = payments or SimulatedUPI123Pay()
    token = None
    if public:
        token = phone_token if phone_token is not None else os.environ.get("PHONE_TOOLS_TOKEN")
        if not token:  # the internet-facing phone port never starts unauthenticated
            raise RuntimeError("PHONE_TOOLS_TOKEN is not set; the public phone port refuses to start")

    @asynccontextmanager
    async def lifespan(_app):
        with sqlite3.connect(db_path) as conn:
            conn.executescript(SCHEMA)
        yield

    app = FastAPI(title="Akshaya-Access Tools API (SIMULATED integrations)", lifespan=lifespan,
                  docs_url=None if public else "/docs", redoc_url=None if public else "/redoc",
                  openapi_url=None if public else "/openapi.json")
    if public:
        expected = f"Bearer {token}"

        @app.middleware("http")
        async def _bearer_auth(request: Request, call_next):
            if request.url.path == "/health":
                return await call_next(request)
            if not secrets.compare_digest(request.headers.get("authorization", ""), expected):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

        # POST /calls exists here, so without this GET /calls would answer 405 and reveal the dashboard route.
        @app.get("/calls")
        def _no_list_calls():
            raise HTTPException(status_code=404)
    else:
        app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"],
                           allow_headers=["*"])

    @app.exception_handler(GuardFailed)
    async def _guard(_req: Request, exc: GuardFailed):
        return JSONResponse({"error": "guard_failed", "reason": exc.reason}, status_code=409)

    @app.exception_handler(NotFound)
    async def _not_found(_req: Request, exc: NotFound):
        return JSONResponse({"error": "not_found", "reason": exc.reason}, status_code=404)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_req: Request, exc: RequestValidationError):
        # Field names only. FastAPI's default 422 echoes the submitted input, which may hold a phone number or secret;
        # an unknown key is itself submitted text, so it is reported as "unknown_field".
        fields = ["unknown_field" if e["type"] == "extra_forbidden" else
                  e["loc"][1] if len(e["loc"]) > 1 and isinstance(e["loc"][1], str) else "body" for e in exc.errors()]
        return JSONResponse({"error": "invalid_request", "fields": list(dict.fromkeys(fields))}, status_code=422)

    @contextmanager
    def tx():
        # One serialized write transaction per request: guards and the writes they protect cannot interleave.
        conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            with conn:  # commits on success, rolls back on any exception (including guard failures)
                conn.execute("BEGIN IMMEDIATE")
                yield conn
        finally:
            conn.close()

    def get_call(c, call_id: str):
        row = c.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,)).fetchone()
        if not row:
            raise NotFound("call_not_found")
        return row

    def open_call(c, call_id: str):
        row = get_call(c, call_id)
        if row["ended_at"]:
            raise GuardFailed("call_ended")
        return row

    def get_bill(c, call_id: str, bill_id: str):
        row = c.execute("SELECT * FROM bills WHERE call_id = ? AND bill_id = ?", (call_id, bill_id)).fetchone()
        if not row:
            raise GuardFailed("bill_not_found")
        return row

    def get_payment(c, payment_id: str):
        row = c.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()
        if not row:
            raise NotFound("payment_not_found")
        return row

    def call_payment(c, call_id: str):
        return c.execute("SELECT * FROM payments WHERE call_id = ? ORDER BY seq DESC LIMIT 1", (call_id,)).fetchone()

    def close_call(c, call_id: str, outcome: str | None):
        if get_call(c, call_id)["ended_at"]:  # ending twice is a no-op
            return
        # The financial outcome comes from the payment service, never from the caller of /end.
        if pay := call_payment(c, call_id):
            outcome = PAYMENT_OUTCOMES[pay["status"]]
        elif outcome in PAYMENT_OUTCOMES.values():
            raise GuardFailed("payment_outcome_without_payment")
        c.execute("UPDATE calls SET state = 'ended', ended_at = ?, outcome = ? WHERE call_id = ?",
                  (now(), outcome, call_id))

    def call_json(c, row) -> dict:
        cid = row["call_id"]
        events = c.execute("SELECT * FROM events WHERE call_id = ? ORDER BY seq", (cid,)).fetchall()
        bill = c.execute("SELECT * FROM bills WHERE call_id = ? AND bill_id = ?", (cid, row["bill_id"])).fetchone()
        pay = call_payment(c, cid)
        hand = c.execute("SELECT * FROM handoffs WHERE call_id = ? ORDER BY seq DESC LIMIT 1", (cid,)).fetchone()
        return {"call_id": cid, "caller_phone_masked": row["caller_phone_masked"], "channel": row["channel"],
                "language": row["language"], "state": row["state"], "outcome": row["outcome"],
                "started_at": row["started_at"], "ended_at": row["ended_at"],
                "events": [event_json(e) for e in events],
                "bill": bill_json(bill) if bill else None,
                "payment": payment_json(pay) if pay else None,
                "handoff": handoff_json(hand) if hand else None}

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/calls", status_code=201)
    def create_call(body: CallIn):
        with tx() as c:
            cid = new_id("call")
            c.execute("INSERT INTO calls (call_id, caller_phone_masked, channel, language, state, started_at) "
                      "VALUES (?, ?, ?, ?, 'greeting', ?)",
                      (cid, mask_phone(body.caller_phone), body.channel, body.language or "ml", now()))
            return call_json(c, get_call(c, cid))

    if not public:  # local dashboard reads never reach the internet-facing phone port
        @app.get("/calls")
        def list_calls(active: bool | None = None):
            where = {None: "", True: "WHERE ended_at IS NULL", False: "WHERE ended_at IS NOT NULL"}[active]
            with tx() as c:
                return [call_json(c, r) for r in
                        c.execute(f"SELECT * FROM calls {where} ORDER BY rowid DESC").fetchall()]

        @app.get("/calls/{call_id}")
        def read_call(call_id: str):
            with tx() as c:
                return call_json(c, get_call(c, call_id))

    @app.post("/calls/{call_id}/events", status_code=201)
    def add_event(call_id: str, body: EventIn):
        with tx() as c:
            open_call(c, call_id)
            seq = c.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE call_id = ?", (call_id,)).fetchone()[0]
            # agent_said lines come from fixed templates and are stored as sent; citizen text is always redacted.
            text, text_en = body.text, body.text_en
            if body.type == "citizen_said":
                text, text_en = redact(text), redact(text_en)
            c.execute("INSERT INTO events (call_id, seq, type, text, text_en, at) VALUES (?, ?, ?, ?, ?, ?)",
                      (call_id, seq, body.type, text, text_en, now()))
            if body.type == "state" and body.text == "ended":
                close_call(c, call_id, "abandoned")  # same as POST /end
            elif body.type == "state":
                c.execute("UPDATE calls SET state = ? WHERE call_id = ?", (body.text, call_id))
            return event_json(c.execute("SELECT * FROM events WHERE call_id = ? AND seq = ?", (call_id, seq)).fetchone())

    @app.post("/calls/{call_id}/end")
    def end_call(call_id: str, body: EndIn | None = None):
        with tx() as c:
            close_call(c, call_id, body.outcome if body else None)
            return call_json(c, get_call(c, call_id))

    @app.post("/tools/fetch_bill")
    def fetch_bill(body: FetchBillIn):
        with tx() as c:
            open_call(c, body.call_id)
            if not body.number_confirmed:
                raise GuardFailed("number_not_confirmed")
            if call_payment(c, body.call_id):  # the payable bill cannot change once collection has started
                raise GuardFailed("payment_already_started")
            # A call has only its current bill. Every fetch is a new selection: the previous bill and its amount
            # confirmation are dropped, so a stale confirm/start for another bill finds nothing.
            c.execute("DELETE FROM bills WHERE call_id = ?", (body.call_id,))
            c.execute("UPDATE calls SET bill_id = NULL WHERE call_id = ?", (body.call_id,))
            bill = biller.fetch_bill(body.consumer_number)
            if not bill:  # returned (not raised) so the cleared selection is committed
                return JSONResponse({"error": "not_found", "reason": "no_bill_for_consumer_number"}, status_code=404)
            c.execute("INSERT INTO bills (call_id, bill_id, consumer_number, customer_name, customer_name_en, "
                      "amount_inr, due_date, simulated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (body.call_id, bill["bill_id"], bill["consumer_number"], bill["customer_name"],
                       bill["customer_name_en"], bill["amount_inr"], bill["due_date"], biller.simulated))
            c.execute("UPDATE calls SET bill_id = ? WHERE call_id = ?", (bill["bill_id"], body.call_id))
            return bill_json(get_bill(c, body.call_id, bill["bill_id"]))

    @app.post("/tools/confirm_amount")
    def confirm_amount(body: ConfirmAmountIn):
        with tx() as c:
            open_call(c, body.call_id)
            get_bill(c, body.call_id, body.bill_id)  # only the call's current bill exists
            c.execute("UPDATE bills SET amount_confirmed = ? WHERE call_id = ? AND bill_id = ?",
                      (body.citizen_confirmed, body.call_id, body.bill_id))
            return bill_json(get_bill(c, body.call_id, body.bill_id))

    @app.post("/tools/start_payment", status_code=201)
    def start_payment(body: StartPaymentIn):
        with tx() as c:
            open_call(c, body.call_id)
            # Exists only if it is the call's current bill, fetched with a confirmed number.
            bill = get_bill(c, body.call_id, body.bill_id)
            # One payment per call, and never a second collection while any call's payment for this bill is pending.
            if c.execute("SELECT 1 FROM payments WHERE call_id = ? OR (bill_id = ? AND status = 'pending')",
                         (body.call_id, body.bill_id)).fetchone():
                raise GuardFailed("payment_already_started")
            if bill["amount_inr"] == 0:
                raise GuardFailed("nothing_due")
            if not bill["amount_confirmed"]:
                raise GuardFailed("amount_not_confirmed")
            pid = new_id("pay")
            status = payments.start_payment(pid, bill["amount_inr"])  # amount comes from the fetched bill only
            c.execute("INSERT INTO payments (payment_id, call_id, bill_id, amount_inr, status, simulated) "
                      "VALUES (?, ?, ?, ?, ?, ?)",
                      (pid, body.call_id, body.bill_id, bill["amount_inr"], status, payments.simulated))
            return payment_json(get_payment(c, pid))

    @app.get("/tools/payment_status/{payment_id}")
    def payment_status(payment_id: str):
        with tx() as c:
            return payment_json(get_payment(c, payment_id))

    @app.post("/tools/handoff", status_code=201)
    def handoff(body: HandoffIn):
        with tx() as c:
            open_call(c, body.call_id)
            case_id = new_id("case")
            used = {r[0] for r in c.execute("SELECT case_number FROM handoffs WHERE status = 'queued'")}
            case_number = secrets.choice([n for n in map(str, range(1000, 10000)) if n not in used])
            c.execute("INSERT INTO handoffs (case_id, case_number, call_id, reason, note, status) "
                      "VALUES (?, ?, ?, ?, ?, 'queued')",
                      (case_id, case_number, body.call_id, body.reason, redact(body.note)))
            return handoff_json(c.execute("SELECT * FROM handoffs WHERE case_id = ?", (case_id,)).fetchone())

    if not public:  # the judge's demo control is local-only
        @app.post("/simulator/payments/{payment_id}/complete")
        def simulator_complete(payment_id: str, body: CompleteIn):
            """SIMULATED demo control standing in for the bank's 123PAY IVR result."""
            if not isinstance(payments, SimulatedUPI123Pay):
                raise NotFound("simulator_disabled")
            with tx() as c:
                pay = get_payment(c, payment_id)
                if pay["status"] != "pending":
                    return JSONResponse({"error": "payment_not_pending", "reason": pay["status"]}, status_code=409)
                status, reference = payments.complete(body.outcome, pay["seq"])
                c.execute("UPDATE payments SET status = ?, reference = ? WHERE payment_id = ?",
                          (status, reference, payment_id))
                return payment_json(get_payment(c, payment_id))

    return app


app = create_app()
