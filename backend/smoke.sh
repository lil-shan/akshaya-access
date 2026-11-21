#!/usr/bin/env bash
# Live smoke test. Starts its own server on a throwaway DB, asserts every status and key value, exits non-zero on the
# first failed check. Usage: ./smoke.sh   (PORT=8765 by default, so a dev server on :8000 is not touched)
set -euo pipefail
cd "$(dirname "$0")"
PORT=${PORT:-8765}; B=http://127.0.0.1:$PORT; PY=.venv/bin/python
TMP=$(mktemp -d); SRV=
cleanup() { if [ -n "$SRV" ]; then kill "$SRV" 2>/dev/null || :; wait "$SRV" 2>/dev/null || :; fi; rm -rf "$TMP"; }
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

# req METHOD PATH WANT_STATUS [JSON_BODY]: prints the response body, fails unless the status matches.
req() {
  local args=(--noproxy '*' -s -o "$TMP/body" -w '%{http_code}' -X "$1") code
  if [ $# -ge 4 ]; then args+=(-H 'Content-Type: application/json' -d "$4"); fi
  code=$(curl "${args[@]}" "$B$2") || fail "$1 $2: no response"
  [ "$code" = "$3" ] || fail "$1 $2 -> HTTP $code, want $3: $(cat "$TMP/body")"
  echo "ok   $1 $2 -> $3" >&2
  cat "$TMP/body"
}
# check JSON PY_EXPR: fails unless the Python expression over `d` (the parsed JSON) is true.
check() { "$PY" -c 'import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if eval(sys.argv[2]) else 1)' "$1" "$2" \
  || fail "check failed: $2 on $1"; echo "ok   $2" >&2; }
get() { "$PY" -c 'import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]])' "$1" "$2"; }

curl --noproxy '*' -s -o /dev/null "$B/health" && fail "something is already listening on port $PORT"
BACKEND_DB_PATH="$TMP/smoke.db" .venv/bin/uvicorn app:app --port "$PORT" --log-level warning & SRV=$!
for _ in $(seq 50); do curl --noproxy '*' -s -o /dev/null "$B/health" && break; sleep 0.2; done
kill -0 "$SRV" 2>/dev/null || fail "server did not start"
[ -f "$TMP/smoke.db" ] || fail "server is not using the smoke DB"

check "$(req GET /health 200)" 'd == {"ok": True}'
CALL=$(req POST /calls 201 '{"caller_phone":"+919876543210","channel":"simulator"}')
check "$CALL" 'd["caller_phone_masked"] == "******3210" and d["state"] == "greeting"'
CID=$(get "$CALL" call_id)
req POST "/calls/$CID/events" 201 '{"type":"agent_said","text":"നമസ്കാരം, ഇത് ഒരു ഡെമോ ആണ്","text_en":"Hello, this is a demo"}' >/dev/null
check "$(req POST "/calls/$CID/events" 201 '{"type":"citizen_said","text":"my pin is 4826"}')" \
  'd["text"] == "my pin is [REDACTED]"'
req POST "/calls/$CID/events" 201 '{"type":"state","text":"fetching_bill"}' >/dev/null
check "$(req POST /tools/start_payment 422 '{"call_id":"x","bill_id":"y","upi_pin":"98765012345"}')" \
  'd == {"error": "invalid_request", "fields": ["unknown_field"]}'
check "$(req POST /tools/fetch_bill 409 "{\"call_id\":\"$CID\",\"consumer_number\":\"1155432100987\",\"number_confirmed\":false}")" \
  'd == {"error": "guard_failed", "reason": "number_not_confirmed"}'
check "$(req POST /tools/fetch_bill 200 "{\"call_id\":\"$CID\",\"consumer_number\":\"1155432100987\",\"number_confirmed\":true}")" \
  'd["bill_id"] == "KSEB-SIM-0001" and d["amount_inr"] == 640 and d["simulated"] is True'
check "$(req POST /tools/start_payment 409 "{\"call_id\":\"$CID\",\"bill_id\":\"KSEB-SIM-0001\"}")" \
  'd["reason"] == "amount_not_confirmed"'
check "$(req POST /tools/confirm_amount 200 "{\"call_id\":\"$CID\",\"bill_id\":\"KSEB-SIM-0001\",\"citizen_confirmed\":true}")" \
  'd["amount_confirmed"] is True'
PAY=$(req POST /tools/start_payment 201 "{\"call_id\":\"$CID\",\"bill_id\":\"KSEB-SIM-0001\"}")
check "$PAY" 'd["status"] == "pending" and d["amount_inr"] == 640 and d["simulated"] is True'
PID=$(get "$PAY" payment_id)

# A second call may not start another collection for the same bill while the first is pending.
CID2=$(get "$(req POST /calls 201 '{"caller_phone":"+919876543210","channel":"simulator"}')" call_id)
req POST /tools/fetch_bill 200 "{\"call_id\":\"$CID2\",\"consumer_number\":\"1155432100987\",\"number_confirmed\":true}" >/dev/null
req POST /tools/confirm_amount 200 "{\"call_id\":\"$CID2\",\"bill_id\":\"KSEB-SIM-0001\",\"citizen_confirmed\":true}" >/dev/null
check "$(req POST /tools/start_payment 409 "{\"call_id\":\"$CID2\",\"bill_id\":\"KSEB-SIM-0001\"}")" \
  'd["reason"] == "payment_already_started"'
check "$(req POST "/calls/$CID2/end" 409 '{"outcome":"paid"}')" 'd["reason"] == "payment_outcome_without_payment"'
check "$(req POST "/calls/$CID2/end" 200 '{"outcome":"abandoned"}')" 'd["outcome"] == "abandoned" and d["ended_at"]'

check "$(req GET "/tools/payment_status/$PID" 200)" 'd["status"] == "pending"'
check "$(req POST "/simulator/payments/$PID/complete" 200 '{"outcome":"confirmed"}')" \
  'd["status"] == "confirmed" and d["reference"]'
check "$(req GET "/tools/payment_status/$PID" 200)" 'd["status"] == "confirmed"'
# The outcome comes from the payment service, not from what /end sends.
check "$(req POST "/calls/$CID/end" 200 '{"outcome":"payment_pending"}')" \
  'd["state"] == "ended" and d["outcome"] == "paid" and d["payment"]["status"] == "confirmed"'
check "$(req POST "/calls/$CID/events" 409 '{"type":"agent_said","text":"x"}')" 'd["reason"] == "call_ended"'

# Handoff gets a speakable case number; a state=ended event closes the call like /end.
CID3=$(get "$(req POST /calls 201 '{"caller_phone":"+919876543210","channel":"simulator"}')" call_id)
check "$(req POST /tools/handoff 201 "{\"call_id\":\"$CID3\",\"reason\":\"citizen_request\",\"note\":\"otp 482913\"}")" \
  'd["status"] == "queued" and len(d["case_number"]) == 4 and d["case_number"].isdigit() and d["note"] == "otp [REDACTED]"'
req POST "/calls/$CID3/events" 201 '{"type":"state","text":"ended"}' >/dev/null
check "$(req GET "/calls/$CID3" 200)" 'd["state"] == "ended" and d["ended_at"] and d["outcome"] == "abandoned"'
check "$(req GET "/calls?active=true" 200)" 'd == []'

curl --noproxy '*' -s -o /dev/null -D "$TMP/headers" -X OPTIONS -H 'Origin: http://localhost:5173' \
  -H 'Access-Control-Request-Method: POST' "$B/calls"
grep -qi '^access-control-allow-origin: http://localhost:5173' "$TMP/headers" || fail "CORS header missing"
echo "ok   CORS allows http://localhost:5173" >&2
echo "SMOKE OK"
