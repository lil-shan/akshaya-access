# Akshaya-Access — status (2026-11-22, overnight build)

## Links
- CRM: https://akshaya-crm-zeta.vercel.app (NOT akshaya-crm.vercel.app — that is someone else's app) — login `crm-tester@akshaya.test`, your own password (`scripts/set-crm-password.sh`)
- Repo: https://github.com/lil-shan/akshaya-access · Supabase: project `akshaya-access` (Mumbai)

## What works (verified end to end on the live database, dummy data, nothing submitted)
| Area | Result |
|---|---|
| Automation unit tests | 82 passed |
| Automation e2e (every service: mock portals with OTP + spoken Sarvam captcha relay, PDFs, Eko bill fetch/pay, UPI QR + simulated payments, DigiLocker sim, guards) | 66 PASS, 0 FAIL |
| Call agent (Sarvam) unit tests | 18 passed |
| Call agent e2e by phone flow: income certificate (mock portal), PMJJBY PDF, KSEB bill + payment | all succeeded, 0 secret leaks |
| Sarvam round trip (Bulbul → Saaras): spoken 13/10-digit numbers | 98/98 digits correct (clean synthetic audio) |
| CRM checks as the test login | 23 PASS, 0 FAIL |
| CRM redesign (frontend-design skill), 18 services in 8 bilingual categories | built, deployed, browser-checked |

## 18 services
Certificates: e-District income / nativity / residence / community / relationship (mock portal), K-SMART birth (mock).
Bills: KSEB, KWA (Eko BBPS mock + UPI QR demo). Insurance: PMJJBY, PMSBY (PDF). Elections: voter Form 6, Form 8 (real-portal
dry run). Identity: PAN 49A prep, passport prep (PDF), ration card add member (mock). Police: Thuna lost property (real-portal
dry run, your password). Agriculture: PMFBY crop loss (PDF). Employment: EPF withdrawal prep (PDF).

## Waiting on you
1. Change your Thuna password (it was pasted in chat), then the live dry runs: cases **100009** (voter Form 6) and
   **100019** (Thuna) → "Dry run on REAL portal". The worker is already running (`logs/worker.log`).
   Expect the first run to stop safely at the first unknown post-login page; tell me and the steps get fixed.
2. `UPI_DEMO_VPA` / `UPI_DEMO_NAME` in `.integrations.env` for the real UPI QR demo.
3. Optional: Eko UAT keys, DigiLocker sandbox keys. Razorpay skipped (needs PAN).
4. `sed -i '2,$d' voice/.env` (junk lines); rotate the Sarvam key after the ideathon (it was pasted in chat).
5. Phone line: rent a Sarvam number (KYC + credits) when you want real calls; the call agent's `--audio` mic mode is untested here.

## Known gaps
- Real-portal post-login steps are [assumed] until your first dry runs.
- Captcha by voice works only for audio captchas (ECI). Image-only portals need WhatsApp (not built). reCAPTCHA portals
  (Passport Seva, PAN, KWA site) can't be relayed by phone.
- Call agent: numbers spoken as words ("fifty thousand") aren't parsed; English portal prompts are read as-is.
- Payments are test/demo only. Going live needs a licensed aggregator flow (RBI PA rules).
