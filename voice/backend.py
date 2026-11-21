"""HTTP client for the backend Tools API, exactly as in contracts/tools-api.yaml. No field carries OTP, PIN or Aadhaar."""
import os

import httpx


class GuardFailed(Exception):
    """HTTP 409: a backend trust rule blocked the action. Never retried."""

    def __init__(self, reason: str):
        super().__init__(f"guard_failed: {reason}")
        self.reason = reason


class BackendError(Exception):
    pass


class Backend:
    def __init__(self, client: httpx.Client | None = None):
        # trust_env=False: citizen data goes straight to the backend, never through a proxy picked up from the environment
        self.http = client or httpx.Client(base_url=os.environ.get("BACKEND_URL", "http://localhost:8000"), timeout=10,
                                           trust_env=False)

    def _call(self, method: str, path: str, body: dict | None = None, none_on_404: bool = False,
              timeout: float | None = None):
        try:
            extra = {} if timeout is None else {"timeout": timeout}
            response = self.http.request(method, path, json=body, **extra)
        except httpx.HTTPError as error:
            raise BackendError(f"{method} {path}: {error}") from error
        if response.status_code == 409:
            raise GuardFailed(response.json().get("reason", "unknown"))
        if response.status_code == 404 and none_on_404:
            return None
        if response.status_code >= 400:
            raise BackendError(f"{method} {path}: HTTP {response.status_code}")
        return response.json()

    def start_call(self, caller_phone: str, channel: str) -> dict:
        return self._call("POST", "/calls", {"caller_phone": caller_phone, "channel": channel, "language": "ml"})

    def event(self, call_id: str, type: str, text: str, text_en: str | None = None) -> dict:
        body = {"type": type, "text": text} | ({"text_en": text_en} if text_en else {})
        return self._call("POST", f"/calls/{call_id}/events", body)

    def end_call(self, call_id: str, outcome: str) -> dict:
        return self._call("POST", f"/calls/{call_id}/end", {"outcome": outcome})

    def fetch_bill(self, call_id: str, consumer_number: str, number_confirmed: bool) -> dict | None:
        """SIMULATED KSEB bill, or None when there is no bill for this number (404)."""
        body = {"call_id": call_id, "biller": "KSEB", "consumer_number": consumer_number, "number_confirmed": number_confirmed}
        return self._call("POST", "/tools/fetch_bill", body, none_on_404=True)

    def confirm_amount(self, call_id: str, bill_id: str, citizen_confirmed: bool) -> dict:
        return self._call("POST", "/tools/confirm_amount",
                          {"call_id": call_id, "bill_id": bill_id, "citizen_confirmed": citizen_confirmed})

    def start_payment(self, call_id: str, bill_id: str) -> dict:
        """SIMULATED UPI 123PAY. The PIN goes from the citizen's keypad to the bank's IVR, never through here."""
        return self._call("POST", "/tools/start_payment", {"call_id": call_id, "bill_id": bill_id})

    def payment_status(self, payment_id: str, timeout: float | None = None) -> dict:
        return self._call("GET", f"/tools/payment_status/{payment_id}", timeout=timeout)

    def handoff(self, call_id: str, reason: str, note: str | None = None) -> dict:
        body = {"call_id": call_id, "reason": reason} | ({"note": note[:500]} if note else {})
        return self._call("POST", "/tools/handoff", body)
