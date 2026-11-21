# Sarvam Voice Agent — phone line setup (dashboard)

Built by the team in the Sarvam dashboard (Voice Agents). Talks to our backend's **public phone port 8001** only
(see README "Phone line via Sarvam Voice Agents"). Items marked **[check]** are not documented by Sarvam; confirm in the tool editor.

## 0. Before you start
1. `scripts/phone-up.sh` → starts backend ports 8000 + 8001 and creates the token file `.phone.env` (gitignored).
2. Expose 8001: `sudo tailscale funnel --bg 8001` (first time: allow Funnel for this device in the Tailscale admin console).
   Public URL = `https://<this-machine>.<tailnet>.ts.net` → call it `BASE` below. Check: `curl BASE/health` → `{"ok":true}`.
3. Sarvam dashboard → **Secrets**: add the value of `PHONE_TOOLS_TOKEN` from `.phone.env` (masked input). Never paste it in a prompt.

## 1. Phone number (paid from Sarvam wallet credits)
Deploy → Phone Numbers → Add Connection → **Rent from Sarvam** → Individual → KYC → buy a number (shows as *Sarvam Vobiz*).
Renews every 30 days from credits; if credits are short the number is released.

## 2. Agent
- Language: **Malayalam** (allow English code-mixing). Voice: Bulbul, a clear calm voice. Model: default.
- Turn-taking: patient (elderly callers) — longest end-of-speech timeout available.

### Instructions (paste as the agent prompt)
```
You are Akshaya-Access, an AI assistant that helps citizens of Kerala pay their KSEB electricity bill by phone.
Speak simple, polite Malayalam. Short sentences. One question at a time. Use English only if the caller does.
This is a DEMO: bills and payments are SIMULATED. Say so in your first turn.

FIRST TURN (always): say you are an AI assistant, this is a demo with simulated payments, the call is processed by a
speech service, and you will NEVER ask for an OTP, UPI PIN or Aadhaar number. Then ask for the 13-digit KSEB consumer number.

HARD RULES
1. Never ask for, repeat, or accept an OTP, UPI PIN, password, card number or Aadhaar number. If the caller starts
   saying one, stop them politely and say you do not need it.
2. Consumer number: it must be exactly 13 digits. Read it back ONE DIGIT AT A TIME in Malayalam and ask "ശരിയാണോ?".
   Only a clear, whole "yes" (അതെ / ശരി / ഉവ്വ് / yes) counts. Anything else (no, a correction, unsure) → ask again.
   After 2 failed attempts → call tool:handoff with reason number_unclear.
3. Only after the caller confirmed the number: call tool:fetch_bill.
4. Read back the customer name and the amount in rupees and ask to confirm. Only a clear whole yes counts.
   Then call tool:confirm_amount. If the amount is 0, say nothing is due and end the call (do not pay).
5. Only after confirm_amount succeeded: call tool:start_payment. Then say: "You will now enter your UPI PIN on your
   phone keypad with your bank's UPI 123PAY line. I cannot hear it and will not ask for it." 
6. Then call tool:payment_status every few seconds, up to about one minute. Report exactly what it returns:
   confirmed (read the reference), failed, or still pending. Never say paid unless status is confirmed.
7. If a tool returns an error or "guard_failed", apologise and call tool:handoff with reason payment_problem.
8. If the caller asks for a person, or for any service other than a KSEB bill, call tool:handoff
   (citizen_request or unsupported_service) and read the case number digit by digit. Do not promise a call back.
9. Never invent a bill, amount, name or payment result. Only say what the tools return.
```

## 3. Tools (API tool, "Real integration")
All: Auth = **bearer token** from the Secret above · Content-Type `application/json` · Max wait 10 s ·
If it fails: "ക്ഷമിക്കണം, ഒരു സാങ്കേതിക പ്രശ്നം ഉണ്ടായി." (Sorry, a technical problem.)

| Name | When | Method + URL | Body | Save reply into variables |
|---|---|---|---|---|
| `start_call` | **on_start** | POST `BASE/calls` | `{"caller_phone": @User Identifier, "channel": "phone", "language": "ml"}` | `call_id` ← `call_id` |
| `fetch_bill` | run | POST `BASE/tools/fetch_bill` | `{"call_id": @call_id, "consumer_number": <13 digits from caller> [check], "number_confirmed": true}` | `bill_id` ← `bill_id` |
| `confirm_amount` | run | POST `BASE/tools/confirm_amount` | `{"call_id": @call_id, "bill_id": @bill_id, "citizen_confirmed": true}` | — |
| `start_payment` | run | POST `BASE/tools/start_payment` | `{"call_id": @call_id, "bill_id": @bill_id}` | `payment_id` ← `payment_id` |
| `payment_status` | run | GET `BASE/tools/payment_status/@payment_id` | — | `payment_status` ← `status` |
| `handoff` | run | POST `BASE/tools/handoff` | `{"call_id": @call_id, "reason": <one of number_unclear, citizen_request, unsupported_service, payment_problem, other> [check]}` | `case_number` ← `case_number` |
| `end_call` | **on_end** | POST `BASE/calls/@call_id/end` | `{"outcome": "abandoned"}` (the backend derives payment outcomes itself) | — |

Response templates:
- fetch_bill: "Name {{customer_name}}, amount ₹{{amount_inr}}, due {{due_date}} (simulated)."
- start_payment: "Payment {{status}} (simulated UPI 123PAY)."
- payment_status: "Payment status: {{status}}, reference {{reference}}."
- handoff: "Case number {{case_number}}."

**[check]** `consumer_number` and handoff `reason` must be parameters the agent fills from the conversation
(function-calling arguments). If the tool editor cannot do that, ask Sarvam's builder assistant (Genie) to create these two tools from this table.

## 4. Deploy
Deploy → Inbound → route the rented number to this agent. Test with Sarvam's **Tests**/playground first
(the demo bill is consumer number 1155432100987 → Rajan K, ₹640). Then dial the number.
Watch the call on the local frontend (`http://localhost:5173`); press **Bank confirms** when the agent waits on the payment.

## Known gaps for the demo
- The live transcript panel stays empty for phone calls (the agent doesn't post lines); bill, payment and handoff cards update.
- Consent strictness and digit-by-digit read-back depend on the prompt, not code. Test them on a call before the demo.
