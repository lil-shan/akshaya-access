"""Integration adapters. Both implementations here are SIMULATED; a real provider replaces them behind the same interface."""
import json
from abc import ABC, abstractmethod
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "contracts" / "fixtures" / "bills.json"
BILL_FIELDS = ("bill_id", "consumer_number", "customer_name", "customer_name_en", "amount_inr", "due_date")


class BillerAdapter(ABC):
    simulated: bool

    @abstractmethod
    def fetch_bill(self, consumer_number: str) -> dict | None:
        """Return the current bill (keys in BILL_FIELDS) or None if the biller has no bill for this number."""


class SimulatedKSEB(BillerAdapter):
    """SIMULATED KSEB biller: serves contracts/fixtures/bills.json (read-only). No network calls."""

    simulated = True

    def __init__(self, fixtures_path: Path = FIXTURES):
        bills = json.loads(Path(fixtures_path).read_text(encoding="utf-8"))["bills"]
        self._bills = {b["consumer_number"]: b for b in bills}

    def fetch_bill(self, consumer_number: str) -> dict | None:
        bill = self._bills.get(consumer_number)
        return {k: bill.get(k) for k in BILL_FIELDS} if bill else None


class PaymentAdapter(ABC):
    simulated: bool

    @abstractmethod
    def start_payment(self, payment_id: str, amount_inr: int) -> str:
        """Ask the provider to collect amount_inr and return the initial status.
        The citizen enters the UPI PIN with their bank; it never passes through this service."""


class SimulatedUPI123Pay(PaymentAdapter):
    """SIMULATED UPI 123PAY: nothing leaves this process. A payment stays `pending` until the demo control
    POST /simulator/payments/{id}/complete stands in for the bank's IVR result."""

    simulated = True

    def start_payment(self, payment_id: str, amount_inr: int) -> str:
        return "pending"

    def complete(self, outcome: str, seq: int) -> tuple[str, str | None]:
        return ("confirmed", f"SIM123PAY-{seq:06d}") if outcome == "confirmed" else ("failed", None)
