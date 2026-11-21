# Akshaya-Access — Implementation Plan (v2, 2026-11-21)

## Product direction v3 (2026-11-21, overrides older sections where they conflict)

- **Remote Akshaya by phone.** Citizens call us (**inbound only, never outbound**). No human operator on our side:
  only the citizen, the voice agent and our automation scripts.
- **CRM is the hub** (Supabase). Voice collects details → CRM case → automation fills the official form → result back to CRM.
  A **service catalogue** (one definition per service: fields, documents, consents, fee, submission method) drives what the
  agent asks, what the CRM shows and what Playwright fills. The service is selectable on the call and in the CRM.
- **Playwright fills portal forms** on the citizen's behalf while they are on the call.
  - OTPs: the citizen reads the OTP the portal sent; used once immediately; never stored, logged or transcribed.
  - Captchas: relayed to the citizen, never solved by OCR/ML. Audio captcha → played to the caller, who says it.
    Image-only captcha → image sent to the caller's WhatsApp, caller reads it out; no smartphone → portal is "later".
  - UPI PIN: never asked; always entered by the citizen with their bank.
- **Testing:** dummy data only; **never submit** on a real portal (dry-run stops before the final submit, with screenshots).
- **Build order:** services that work 100% end to end with dummy data first; the rest later. Voice/phone after the automation works.
- Providers (DigiLocker, UPI, BBPS): cheapest / free sandboxes — see `reviews/research-07-providers.md`.

## Ideathon prototype scope (this section overrides the rest for the build)

Decided by the team on 2026-11-21:
- **Payment is UPI over the phone call (UPI 123PAY style)** — works on a feature phone. The agent hands off to the
  UPI 123PAY step; the citizen enters the UPI PIN on the keypad to the bank's IVR, never to our agent.
- **No one-time registration.** The caller says the consumer number; the agent reads it back digit by digit and asks to confirm.
- **Business model, funding and the operator economics are out of scope** for the build.
- Integrations that need approvals (BBPS, 123PAY, KSEB) are **SIMULATED** behind one adapter each, labelled as such (deck slide 4 allows this).
- Speech credits available: **Sarvam 600 credits** (primary: Saaras STT + Bulbul TTS for Malayalam) and **Smallest.ai $50**
  (backup TTS only, added later only if Bulbul's Malayalam voice tests poorly). Keys go in `voice/.env`, set by the team.

Demo flow to build (deck slide 4):
1. Citizen calls; agent greets in Malayalam, says it is an AI and never asks for OTP/PIN.
2. Citizen says the KSEB consumer number → digit-by-digit read-back → "yes" / correction.
3. Backend fetches the bill (simulated) → agent reads back name and amount → citizen confirms.
4. Agent hands off to UPI 123PAY (simulated); citizen "enters PIN" on the keypad to the bank IVR side.
5. Agent reports **confirmed / failed / pending** from the payment service; pending is said as pending.
6. Uncertain or unsupported → handoff to a human (logged case).

Parts: `voice/` (call + Malayalam conversation + text simulator), `backend/` (Tools API, simulated adapters, cases,
guards), `frontend/` (judge-facing live view of the call and case status). Interfaces in `contracts/`.

The sections below are the longer-term plan and research context.

Research: `research/01-voice-language-stack.md`, `02-govt-payment-integrations.md`, `03-regulation-risk-precedents.md`.
Critiques of v1 (Opus, Fable, Sonnet): `research/critiques/`. **[unverified]** = confirm before depending on it.

## 0. What changed from v1, and why

All three reviewers independently found the same failures in v1:

| v1 assumption | Problem | v2 change |
|---|---|---|
| Caller pays via a UPI link sent to their phone | The target user (elderly, basic phone) has no WhatsApp/UPI. Smartphone+UPI users already have WhatsApp's own bill pay | **Nominated payer**: a child, relative or the operator, registered once with consent. "Pay cash at the KSEB office" also counts as success. Metric = *bill paid within 48 h*, not "link sent" |
| Caller dictates a 13-digit consumer number each time | Even at 98% per digit, the whole number is right only ~77% of the time. Keypad (DTMF) support in Sarvam is unconfirmed | **One-time registration at an Akshaya centre**: the operator enters the consumer number(s) and payer number against the caller's phone. Repeat calls need no digits |
| Build bill pay first; claim packs in May–Jul | Bill pay is the most competed-on feature, and demand was assumed, not observed | **December concierge pilot** finds out what callers actually ask for before we build beyond the core |
| Operators paid per handoff *and* paying per case | Contradictory; citizens can't be charged extra (Kerala HC 2025); bill pay may not be Akshaya revenue anymore [unverified 2024 report] | **Operators gain referrals** for fee-bearing services at official rates. The **state/LSG or a grant** pays us |
| Feb build week: phone + WhatsApp bot + API + operator page + 20 user sessions | Overloaded; sandbox "payments" with real elderly users prove nothing and burn trust | **Feb = phone only** + operator registration page. Real-user sessions only after production BBPS |
| Claim packs with Aadhaar/PAN photos | Breaks our own "never handle Aadhaar" rule | Checklist-first; masked Aadhaar only; DigiLocker only when a need is measured |

Kept from v1 (all three reviewers agreed): inbound-only calls; never holding money, PINs or OTPs; postfunded BBPS through an aggregator; one agent per channel plus one Tools API (no multi-agent orchestration); trust rules enforced in code; digit-by-digit read-back; India hosting; a dated knowledge base that refuses when stale; Pipecat as the lock-in fallback.

## 1. Who it is for, and what it does

**Primary user:** an elderly Malayalam speaker on a basic phone, with a family member or an Akshaya operator in the background. **Secondary user:** migrant workers (Hindi later).

| Kind | v2 scope |
|---|---|
| **Bills** (KSEB, then KWA) | "Your bill is ₹640, due on the 12th. Shall I ask Anu to pay?" → link to the nominated payer → voice/SMS confirmation to the caller |
| **Information** | ~20 frequent questions (pension mustering, ration card, document lists), each with a source and date |
| **Preparation** | Claim checklists (PMJJBY/PMSBY) first; full packs only if the concierge pilot shows demand |

## 2. Architecture (unchanged in shape, smaller in scope)

```
Phone (inbound) ─► Sarvam Voice Agent ──tool calls──► Tools API ◄── Operator page (register citizen,
                                                          │                       see handoffs)
WhatsApp (payer only: link + receipt) ◄───────────────────┤
                                                          ├─► BBPS aggregator (fetch, pay, status)
                                                          └─► Postgres, India region
                                                              (citizens, payers, consents, cases, events)
```

- **Tools:** `identify_caller(phone)`, `fetch_bill(consumer_no)`, `notify_payer(case_id)`, `get_payment_status(case_id)`, `create_handoff(case_id, reason)`, `lookup_info(topic)`.
- **Identity check:** confirm by the BBPS customer name ("Is the bill in the name of Rajan K?") instead of repeated digit read-back [unverified that KSEB fetch returns the name].
- **Unregistered callers:** they may dictate the number (read back digit by digit, then confirm the name). Otherwise: "Please visit [centre] once to register."
- **Handoff:** live transfer to the operator during centre hours if Sarvam supports it (reviewers disagree, so ask Sarvam); otherwise a callback list with a stated response time.
- **WhatsApp voice-note bot:** deferred. Sarvam's WhatsApp agent is enterprise-only, and WhatsApp users already have native bill pay.

## 3. Trust rules (in code)

1. Short opener (test it for hang-ups): "Akshaya-Access AI assistant. This call is recorded. We never ask for OTP, PIN or Aadhaar. Shall we continue?" Log consent.
2. `notify_payer` refuses unless the case has a registered or confirmed consumer number, a BBPS-fetched amount, and a consented payer.
3. Status comes only from the aggregator. Pending is said as pending.
4. The payer consents separately ("acting on behalf of" flow, DPDP).
5. No Aadhaar or PAN numbers are stored. Documents, when added later, are encrypted and auto-deleted 30 days after case closure.

## 4. Phases

### Phase 0: December 2026 (decides whether and what to build)

| # | Task | Owner | Done when |
|---|---|---|---|
| 1 | **Decide the legal entity** (it gates BBPS, WABA, telephony KYC, contracts) | Founders | Registered / KYC docs ready |
| 2 | **Ask Sarvam in writing:** DTMF? live call transfer? Malayalam digit accuracy? Kerala references? | Tech | Written answer. If no DTMF, plan Pipecat + Exotel/Plivo IVR for digit entry |
| 3 | **Concierge pilot** at 2 Ernakulam centres: publish a number, a Malayalam-speaking person answers using the script, logs every request type, and tries the nominated-payer flow by hand | Ops | ≥50 calls logged. We know the bills / info / claims split and how bills actually get paid |
| 4 | **Digit test set:** record 30+ consenting elderly speakers (phone audio, mixed dialects) reading consumer numbers. Run it through Saaras v4, plus Azure or Google for comparison | Tech | Per-number accuracy measured |
| 5 | **Interview 8–10 Akshaya operators:** where their time goes, what they would value, whether KSEB bills still pass through them | Ops | Written notes |
| 6 | Approach the **Akshaya State Project Office / KSITM** and **KSUM / Digital University Kerala** (grant, Malayalam AI mission) | Founders | First meeting held |
| 7 | Apply to a **BBPS aggregator** (Setu / Cashfree / Razorpay), postfunded; get the KSEB/KWA biller IDs and a sample fetch response | Tech | Sandbox keys; confirmed biller IDs and name field |

**Go/no-go gate (mid-January):**
- Concierge data shows real demand.
- Digit accuracy, or the registration route, is workable.
- The entity and BBPS application are moving.
- Re-rank bills vs claims by the concierge data.

### Phase 1: build week, 1–7 Feb 2027

- Sarvam phone agent: identify the caller, fetch the bill (sandbox, or real read-only if live), read the amount and name, notify the payer (sandbox), hand off.
- Tools API + Postgres + a minimal operator page (register a citizen and payer, list handoffs).
- **Exit:**
  - The test set passes through the full call flow.
  - Every guard in §3 has a test.
  - **No real users on simulated payments.**

### Phase 2: supervised live pilot (Mar–Apr 2027)

- Production BBPS (KSEB, then KWA, the same integration). 2 centres, ~50 registered citizens.
- Measure:
  - bills paid within 48 h
  - calls completed without a handoff
  - hang-up rate on the opener
  - operator minutes saved or spent
- Add `lookup_info` with the ~20 curated questions.

### Phase 3: claims (May 2027+, only if Phase 0/2 data supports it)

- PMJJBY/PMSBY: checklist and deadline reminders by voice. The family or operator assembles the pack; masked Aadhaar only.
- Upload and pack generation, plus DigiLocker via a reseller, only after legal sign-off on retention and masking.

### Phase 4: expansion

Hindi for migrant workers, more services, consented reminders, but only after the TRAI A2P rules are confirmed for our number type.

## 5. Cost

- **Pilot telephony + AI:** about ₹3,000–3,500 per 100 calls, including GST, plus a WhatsApp BSP fee (payer messages only, likely within the 1,000 free service messages per month), hosting (~₹1–3k/month) and aggregator fees [unverified].
- **Concierge pilot:** one part-time Malayalam speaker for 2 weeks, plus a phone number.

## 6. Who pays

Citizens pay only official charges. We are funded by a grant (KSUM, Malayalam AI mission, IndiaAI CoE at DUK) or an LSG/state pilot contract. Operators gain registrations and referrals for fee-bearing services at official rates. BBPS commission is assumed to be zero until quoted.

## 7. Top risks

| Risk | Mitigation |
|---|---|
| Elderly users won't talk to an AI | Concierge pilot first; operator introduces it at registration |
| Digit errors | Registration removes digits on repeat calls; name confirmation; DTMF via IVR if needed |
| No one pays the nominated-payer link | Measured in the concierge pilot; cash at the KSEB office counts as an outcome |
| Operators resist | Interviews first; registration and referrals benefit them; MoU via the State Project Office |
| Entity/BBPS delays | Start in December; Feb build doesn't depend on production |
| Scam clones | One published number, Akshaya posters, "we never ask OTP" |
| DPDP (full by ~May 2027) | Consent log, proxy consent, retention, erasure from day one |
| Sarvam lock-in / gaps | We own the Tools API; Pipecat + Sarvam STT/TTS + Exotel/Plivo as fallback. Smallest is not a near-term fallback (Lightning v3.1 retires 30 Nov 2026) |

## 8. Decisions needed from the team now

1. Which legal entity applies?
2. Which 2 centres, and who runs the concierge line?
3. Is 1–7 Feb fixed (grant/competition), or can the build follow the January gate?
