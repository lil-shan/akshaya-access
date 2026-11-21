# Research 3: Regulation, risks, precedents, funding (Sonnet agent, 2026-11-21)

Secondary sources mostly; verify primary texts before relying on rule numbers/dates.

## Legal must-dos (ranked)
1. **DPDP Act + Rules (notified Nov 2025, phased).** Consent managers ~12 months (≈ now); notices, security, breach notification, retention, rights ≈ 18 months (~May 2027, approximate). Do: standalone Malayalam notice; logged voice/WhatsApp consent; encryption + access control; processor contracts with Sarvam / telephony / WhatsApp BSP / payment gateway; ≥1-year logs; 72h breach reporting; erasure + grievance channel. "Acting on behalf of a parent" needs an explicit flow. Sources: Baker Botts, YourStory, dpdpa.com s.9.
2. **Aadhaar: don't handle it.** Masked only; unlicensed collection/retention of Aadhaar copies is risky; private e-KYC needs approval (Jan 2025 amendment); Aadhaar Data Vault rules. Never take Aadhaar numbers by voice. Sources: Khaitan, UIDAI ADV FAQ (Nov 2025).
3. **DigiLocker requester onboarding**: eligibility review, official-domain email, India-hosted server, requester ToU (June 2025). Until then: user-shared docs, delete after task.
4. **Payments: never touch funds.** BBPS (BBPOU) or licensed PA; UPI link to the user; never PIN/OTP. RBI BBPS Master Direction 2024.
5. **Calls/TRAI.** No specific recording statute; disclose "AI assistant, recorded, say yes" and log. TRAI tightening on automated/AI calls (status unclear). Be inbound-first; outbound needs consent + registration.
6. **Akshaya fees are government-fixed** (GO(Rt) 185/2025/ITD; Kerala HC Sept 2025: only govt sets charges). Don't add citizen fees on top; MoU with Akshaya State Project Office / KSITM; charge operators or the state.

## Risks → mitigations
- Digit/name errors (elderly speech hurts ASR; no Malayalam elderly digit benchmarks found) → digit-by-digit read-back, DTMF keypad fallback, operator handoff, measure on own recordings.
- Trust/fraud fears + AI voice-clone scams → first sentence: "I will never ask for OTP/PIN/Aadhaar"; one published number + verified WhatsApp; Akshaya posters.
- Impersonation of the service → publish official number; money only to named billers via user-verified links.
- Wrong advice on pensions/claims → operator reviews before submission; status only from authoritative sources.
- Vendor data residency → contract: India-resident, no training use.

## Precedents
- **Sarvam × NHA**: 1.4M citizens reached in 6 days, outbound awareness (53% connect, 28% interested, 16% willing). Awareness, not transactions.
- **Jugalbandi** (WhatsApp, 10 langs, 171 schemes): "rough edges", no usage data. Info ≠ completed applications.
- **Haqdarshak**: human-assisted agents + tech; ~6.7M citizens, ₹19,232 cr benefits. Strongest evidence for operator-in-the-loop.
- **UMANG / DigiLocker / MyGov WhatsApp**: huge registrations; the assisted last mile is the gap.
- **Akshaya**: operators' economics already strained — if the AI cuts their income, they resist.

## Partnership / funding
KSUM innovation grants (check current); Kerala Budget 2026-27 Malayalam AI mission + startup fund (reported); Digital University Kerala AI CoE (IndiaAI, May 2026) — also a Malayalam ASR eval partner; KSITM / Akshaya State Project Office for pilot MoU; Bhashini/CSR — no specifics found.

## Not verified
Exact DPDP dates/penalties/72h; TRAI AI-call amendment status; any legal AI-disclosure requirement; UIDAI circular text; DigiLocker requester eligibility text; full Akshaya fee schedule; any Kerala Sarvam pilot; Malayalam elderly digit accuracy; KSUM current grants; Bhashini terms; Smallest.ai data practices.
