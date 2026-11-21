# Research 2: Government & payment integrations (Fable agent, 2026-11-21)

## Bottom line
- **KSEB/KWA bill pay is feasible in ~3 months** as a BBPS (Bharat Connect) *agent institution* under a licensed aggregator (Setu, Cashfree, PayU, Razorpay, BillAvenue). Setu quotes 2–3 weeks to go live. Bill fetch returns customerName, amount, dueDate, billNumber (generic schema).
- **No money held**: choose *postfunding* (citizen pays into aggregator/BBPS escrow). Prefunding = you float your own money.
- **UPI collect is dead** (P2P ended 1 Oct 2025; merchant collect deprecated 28 Feb 2026 per gateways). Use UPI intent links / QR on WhatsApp — PIN entered in the citizen's own UPI app.
- **Kerala state portals are portal-only** (login/OTP/captcha): KSEB, KWA, K-SMART, e-District, ReLIS, Thuna, civil supplies, Sevana. Agent can guide and prepare, not transact.
- **Competition**: WhatsApp native bill payments on Bharat Connect (3 Sep 2026, 22,722 billers); Setu "agentic bill payments" on Claude/ChatGPT (9 Dec 2025).

## Feasibility table
| Service | Route | Access needs | 3-mo feasibility | Source |
|---|---|---|---|---|
| DigiLocker direct | API Setu partner; OAuth2+PKCE; citizen consents on DigiLocker page | Indian entity (startups ok), website, official email, DSC, India-hosted server, nodal officer, committee review, STQC audit | Med | cf-media.api-setu.in/resources/Partners-SOP.pdf |
| DigiLocker via reseller | Setu, Cashfree, Digio, Signzy, HyperVerge | Contract; Setu ~₹4/verification | High | setu.co/data/kyc/digilocker |
| DigiLocker docs | Aadhaar, PAN, DL, RC solid; Kerala certificates uncertain | Kerala "certificate-less governance" phase I targets ~100 certs | Med/Low | pib.gov.in PRID=2195454 |
| API Setu | Consumer registration per API | PAN, GST, incorporation, use case; publisher approval | Med | docs.apisetu.gov.in |
| BBPS KSEB + KWA | Agent institution under COU aggregator | Both listed as billers by aggregators/banks | High | setu.co/payments/bbps/cou |
| UPI intent in WhatsApp | Meta Payments API India (Razorpay/PayU deep) or Setu WhatsApp Collect | WABA via BSP, gateway account, templates; ~2 weeks | High | developers.facebook.com …/payments-in/overview |
| UPI Circle | Not an API — family sets it up | Full delegation ₹15k/month, ₹5k/txn | Advisory | NPCI press release 2024 |
| UPI 123PAY | IVR/missed-call pay; PIN to bank IVR | Via gateway offering it; limit ₹5k–10k | Med | npci.org.in upi-123pay faqs |
| RBI PA licence | Avoid — never pool funds | ₹15 cr net worth | Don't | RBI PA Master Directions |
| K-SMART | Portal/app only; IKM EOI (Jan 2026) for API certificate *verification* | No 3rd-party data transfer | Low | ikm.gov.in/en/node/1159 |
| e-District, ReLIS, ration, Sevana | Portal-only | Pension mustering biometric at Akshaya | Low | — |
| Kerala Police Thuna/Pol-App | Portal/app | FIR download by no./year/station; accident GD entry; lost-property certificate | Low (guide) | thuna.keralapolice.gov.in |
| Akshaya | Individual entrepreneur licence, not a company franchise | — | Partner informally | onmanorama 2026-03-13 |
| PAN | e-PAN on IT portal / Protean | Citizen Aadhaar OTP | Low (guide) | — |
| Passport | Online form + slot | Biometrics at PSK | Low (prep) | passportindia.gov.in |
| Voter (ECI) | Forms 6/7/8 | Aadhaar e-sign | Low | — |
| Parivahan (Kerala MVD) | Sarathi/Vahan | 60 more services Aadhaar-OTP from 21 Sep 2026 | Low | onmanorama 2026-08-31 |
| EPFO | Member portal/UMANG | UAN + Aadhaar OTP, face auth | Low | — |
| PMJJBY/PMSBY claims | Document prep; filed at bank/post office | see below | **High** | Kotak / India Post SOPs |
| PM-JAY/KASP | beneficiary.nha.gov.in, helpline 14555 | No citizen status API | Low | — |
| PMFBY | Helpline 14447 / app | Loss report within 72h | Med (reminders) | PIB |

## Insurance claim details
- **PMJJBY (₹2 lakh)**: nominee files claim-cum-discharge form at bank/PO, preferably within 30 days. Docs: death proof, Aadhaar/PAN of deceased & claimant, claimant KYC, passbook/cancelled cheque, discharge receipt, succession cert if no nominee. Bank forwards in 7 days; insurer settles in 7. No claim for non-accidental death in first 30 days of enrolment.
- **PMSBY**: within 30 days of accident. Death: original FIR/panchnama, post-mortem report, death certificate. Disability: FIR/panchnama + civil surgeon certificate.
- Kerala sources: FIR via Thuna/Pol-App; death certificate via K-SMART.

## Not verified
Official NBBL biller IDs for KSEB/KWA and whether KSEB fetch returns name; Setu BBPS pricing/funds flow; NBBL agent eligibility; DigiLocker direct timeline/fees; Kerala certs on DigiLocker; reseller pricing (except Setu); P2M collect circular text; UPI Circle 2026 limits; 123PAY limit; whether 3rd-party bots can use WhatsApp native bill pay; 11 Nov 2026 PA update; post-mortem copy procedure in Kerala; KSITM partnership route; KASP status channels; land tax on BBPS; PAN 2.0 / Passport Seva 2.0 details.
