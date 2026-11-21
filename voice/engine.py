"""The call: a deterministic state machine (no LLM) over the contract's Call states.

`io` needs two methods: listen() -> the citizen's next line (None = hung up), and
show(kind, text, text_en, both) to print/speak a line (kind: agent | citizen | state | note).
The citizen is only listened to while collecting/confirming the number and confirming the amount -
never during the PIN step, which happens between the citizen's keypad and the bank.
"""
import math
import time

import lines
from backend import Backend, BackendError, GuardFailed
from parsing import digits_ml, parse_digits, parse_yes_no, wants_other_service, wants_person

NUMBER_LENGTH = 13
MAX_NUMBER_ATTEMPTS = 2
STATUS_REQUEST_TIMEOUT = 10.0  # seconds; never more than what remains of the polling deadline
PAYMENT_OUTCOMES = {"confirmed": "paid", "failed": "payment_failed", "pending": "payment_pending"}


class _Handoff(Exception):
    def __init__(self, reason: str, why: str, note: str | None = None):
        self.reason, self.why, self.note = reason, why, note


class _HungUp(Exception):
    pass


class Engine:
    def __init__(self, backend: Backend, io, poll_interval: float = 2.0, poll_timeout: float = 60.0, sleep=time.sleep,
                 clock=time.monotonic):
        if not (math.isfinite(poll_interval) and poll_interval > 0):
            raise ValueError("poll_interval must be a positive, finite number of seconds")
        if not (math.isfinite(poll_timeout) and poll_timeout >= 0):
            raise ValueError("poll_timeout must be a finite number of seconds, 0 or more")
        self.backend, self.io = backend, io
        self.poll_interval, self.poll_timeout, self.sleep, self.clock = poll_interval, poll_timeout, sleep, clock
        self.state = "greeting"
        self.outcome = self.call_id = self.number = self.bill = self.payment = None
        self.status_unreadable = False
        self.failed_attempts = 0

    def run(self, caller_phone: str, channel: str) -> str:
        self.call_id = self.backend.start_call(caller_phone, channel)["call_id"]
        try:
            try:
                try:
                    while self.state not in ("done", "handed_off"):
                        getattr(self, f"_{self.state}")()
                except GuardFailed as guard:  # explain and hand off; never retry around a guard
                    note = f"guard_failed: {guard.reason}"
                    raise _Handoff("payment_problem" if self.state == "paying" else "other", "guard", note) from guard
            except _Handoff as handoff:
                self._hand_off(handoff)
            except (_HungUp, KeyboardInterrupt):  # Ctrl-C in the simulator = the citizen hangs up
                pass
        except (BackendError, GuardFailed):
            self._technical_problem()
            try:
                self._close()
            except (BackendError, GuardFailed):
                pass
            raise
        return self._close()

    def _close(self) -> str:
        """End the call. A payment outcome is sent only when a payment exists, and then it is the last status seen;
        the backend's own answer (it asks the payment service) is the final outcome."""
        if self.payment:
            sent = PAYMENT_OUTCOMES[self.payment["status"]]
        else:
            sent = self.outcome if self.outcome not in PAYMENT_OUTCOMES.values() else None
        sent = sent or "abandoned"
        self.outcome = self.backend.end_call(self.call_id, sent).get("outcome", sent)
        return self.outcome

    def _technical_problem(self):
        line = lines.TECH_PROBLEM_PAYMENT if self.payment else lines.TECH_PROBLEM
        try:
            self.backend.event(self.call_id, "agent_said", line[0], line[1])
        except (BackendError, GuardFailed):
            pass
        self.io.show("agent", line[0], line[1], False)

    # --- states ---

    def _greeting(self):
        self._say(lines.OPENING, both=True, critical=True)
        self._say(lines.ASK_NUMBER)
        self._go("collecting_number")

    def _collecting_number(self):
        digits = parse_digits(self._hear())
        if len(digits) != NUMBER_LENGTH:
            return self._number_failed(lines.WRONG_LENGTH, n=len(digits))
        self.number = digits
        self._go("confirming_number")

    def _confirming_number(self):
        self._say(lines.READ_BACK_NUMBER, critical=True, digits_ml=digits_ml(self.number), digits_en=" ".join(self.number))
        if self._hear_yes_no():
            self._go("fetching_bill")
        else:
            self._number_failed(lines.NUMBER_AGAIN)

    def _fetching_bill(self):
        self._say(lines.CHECKING_BILL)
        self.bill = self.backend.fetch_bill(self.call_id, self.number, number_confirmed=True)
        if self.bill is None:
            return self._number_failed(lines.BILL_NOT_FOUND)
        if self.bill["amount_inr"] == 0:
            self._say(lines.NOTHING_DUE, **self._bill_words())
            return self._finish("nothing_due")
        self._go("confirming_amount")

    def _confirming_amount(self):
        self._say(lines.READ_BACK_BILL, critical=True, **self._bill_words())
        confirmed = self._hear_yes_no()
        self.backend.confirm_amount(self.call_id, self.bill["bill_id"], citizen_confirmed=confirmed)
        if confirmed:
            return self._go("paying")
        self._say(lines.DECLINED)
        self._finish("abandoned")

    def _paying(self):
        self.payment = self.backend.start_payment(self.call_id, self.bill["bill_id"])
        self.io.show("note", f"payment {self.payment['payment_id']} started (SIMULATED UPI 123PAY); waiting for the bank result")
        self._say(lines.PIN_HANDOFF, both=True)
        deadline = self.clock() + self.poll_timeout
        while True:  # the status comes only from the payment service
            remaining = deadline - self.clock()
            try:
                self.payment = self.backend.payment_status(
                    self.payment["payment_id"], timeout=min(STATUS_REQUEST_TIMEOUT, max(1.0, remaining)))
                self.status_unreadable = False
            except BackendError:
                self.status_unreadable = True  # keep the last known status; try again until the deadline
            if self.payment["status"] != "pending":
                break
            remaining = deadline - self.clock()
            if remaining <= 0:
                break
            self.sleep(min(self.poll_interval, remaining))
        status = self.payment["status"]
        if status == "confirmed":
            self._say(lines.PAID, amount=self.payment["amount_inr"], reference=self.payment.get("reference") or "-")
            self._finish("paid")
        elif status == "failed":
            self._say(lines.PAYMENT_FAILED)
            self._finish("payment_failed")
        else:
            self._say(lines.STATUS_UNKNOWN if self.status_unreadable else lines.PAYMENT_PENDING)
            self._finish("payment_pending")

    # --- helpers ---

    def _number_failed(self, line, **values):
        self.failed_attempts += 1
        if self.failed_attempts >= MAX_NUMBER_ATTEMPTS:
            raise _Handoff("number_unclear", "number_unclear")
        self._say(line, **values)
        self._go("collecting_number")

    def _hand_off(self, handoff: _Handoff):
        case = self.backend.handoff(self.call_id, handoff.reason, handoff.note)
        number = case["case_number"]
        why_ml, why_en = lines.HANDOFF_WHY[handoff.why]
        self._say((f"{why_ml} {lines.HANDOFF[0]}", f"{why_en} {lines.HANDOFF[1]}"), note=handoff.note,
                  case_ml=digits_ml(number), case_en=" ".join(number))
        self._go("handed_off")
        self.outcome = "handed_off"

    def _finish(self, outcome: str):
        self.outcome = outcome
        self._go("done")

    def _bill_words(self) -> dict:
        bill = self.bill
        return {"name": bill["customer_name"], "name_en": bill.get("customer_name_en") or bill["customer_name"],
                "amount": bill["amount_inr"]}

    def _go(self, state: str):
        if state != self.state:
            self.state = state
            self._post("state", state)

    def _say(self, line, both: bool = False, critical: bool = False, **values):
        """`both` = trust-critical line that audio mode speaks in Malayalam and then English.
        `critical` = the citizen must hear it before answering; if it was not played, record that and hand off."""
        played = self._post("agent", line[0].format(**values), line[1].format(**values), both)
        if played is False:
            self.backend.event(self.call_id, "agent_said", *lines.NOT_PLAYED)
            self.io.show("note", *lines.NOT_PLAYED)
            if critical:
                raise _Handoff("other", "not_played", "a line could not be played to the citizen")

    def _post(self, kind: str, text: str, text_en: str = "", both: bool = False):
        self.backend.event(self.call_id, "state" if kind == "state" else f"{kind}_said", text, text_en)
        return self.io.show(kind, text, text_en, both)

    def _hear_yes_no(self) -> bool:
        """Only a whole affirmative reply is yes. Unclear -> ask once more, then treat as no."""
        answer = parse_yes_no(self._hear())
        if answer is None:
            self._say(lines.ONLY_YES_NO)
            answer = parse_yes_no(self._hear())
        return answer is True

    def _hear(self) -> str:
        """Next citizen line. Only what was understood is posted and shown, never the words themselves."""
        said = self.io.listen()
        if said is None:
            raise _HungUp
        digits = parse_digits(said)
        if wants_person(said):
            key = "person"
        elif wants_other_service(said):
            key = "service"
        elif self.state == "collecting_number":
            key = "number" if len(digits) == NUMBER_LENGTH else "unclear"
        else:
            key = {True: "yes", False: "no"}.get(parse_yes_no(said), "unclear")
        ml, en = lines.HEARD[key]
        self._post("citizen", ml.format(number=digits), en.format(number=digits))
        if key == "person":
            raise _Handoff("citizen_request", "citizen_request")
        if key == "service":
            raise _Handoff("unsupported_service", "unsupported_service")
        return said
