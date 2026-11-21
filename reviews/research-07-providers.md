# Research 07 — Cheapest/free sandboxes: DigiLocker, UPI collection, BBPS

Date: 2026-11-21 · Author: Devin review worker · Context: Akshaya-Access prototype team, no registered company yet.
All claims cite official docs/pricing where possible; **[unverified]** = third-party or could not confirm on the vendor's own pages. Prices change — re-check before paying.

## 1. DigiLocker document fetch (citizen consent)

| Provider | Sandbox without a company | Signup needs | Free tier | Live price | Notes |
|---|---|---|---|---|---|
| API Setu direct (requester) | No real sandbox keys; approval-gated | Registered Indian org (GSTN is validated; errors for invalid GSTN), nodal-officer Aadhaar OTP, committee approval, signed ToS | Platform itself is free (MeitY) | No published fee; post-live duties: quarterly usage report + STQC audit | https://api.apisetu.gov.in/ · https://www.digilocker.gov.in/assets/FAQ%20DL%20EL_onboarding.pdf · eligibility detail [unverified] https://didit.me/blog/digilocker-api/ |
| API Setu sandbox | **Yes — no sign-up at all** | None | Fully free | n/a (sample data only) | Hosted playground with pre-filled data for the DigiLocker OAuth + doc-fetch endpoints. Good for learning the request/response shape; not your own client_id for a real app. https://sandbox.api-setu.in/ · https://docs.apisetu.gov.in/document-central/explore-apisetu/Sandbox.html |
| Setu DigiLocker | Sandbox exists (`dg-sandbox.setu.co`) but credentials only via sales contact | "Contact Setu" for x-client-id/secret/product-instance | No self-serve free tier | Not published | https://docs.setu.co/data/digilocker/quickstart |
| Cashfree SecureID | Sandbox exists (`sandbox.cashfree.com/verification`) | Merchant signup; "Verify My Customers" product requires business PAN during onboarding | Sandbox free | Prepaid/postpaid, sales-quoted | **Caveat:** Cashfree docs state the DigiLocker flow in sandbox needs *real* Aadhaar numbers/live DigiLocker data — no mock Aadhaar. https://www.cashfree.com/docs/secure-id/digilocker/digilocker · https://www.cashfree.com/docs/help/account/account-activation |
| Surepass | UAT (`sandbox.surepass.app`) but token from sales manager only | API-key request form → sales callback (no self-serve) | Sandbox after onboarding | Not published | https://surepass.io/get-api-key/ · https://github.com/surepassio/surepass-digiboost-web-sdk |
| Digio | Trial/sandbox advertised on site [unverified] | Signup form; production sales-gated | Small trial [unverified] | Not published | https://digio.in |
| IDfy | **Yes — SelfServe portal** | apicentral.idfy.com signup, "no credit card required for trial" | Free trial | Not published | https://apicentral.idfy.com/sessions/new |
| Signzy | Sandbox exists | API key via contact team; startup program gives ₹5,000 free sandbox credits | ₹5,000 credits (startup program) | Not published | https://www.signzy.com/fintech-apis/startups · https://docs.signzy.com/us-apis |
| HyperVerge | Marketplace integration, sales-gated | Contact/chat | None public | Not published | https://hyperverge.co/in/integrations-marketplace/digilocker-api/ |
| Veriqos (not on the brief's list, worth noting) | **Yes — self-serve sandbox, no sales call** | sandbox.veriqos.com signup | Sandbox free | Not published [unverified] | https://veriqos.com/vs/surepass/ |

## 2. UPI payment collection (test demos)

| Provider | Test mode w/o KYC | UPI features in test | Live MDR/platform fee | WhatsApp | Notes |
|---|---|---|---|---|---|
| Razorpay | **Yes — instant after signup, unlimited duration** | UPI intent + standard payment links payable in test; **UPI payment links are live-mode only**; QR Codes need a separate enablement request | 2% platform fee on all domestic incl. UPI (+GST) | Official "Payments on WhatsApp" product (needs WhatsApp Business Account) | https://razorpay.com/docs/payments/dashboard/test-live-modes · https://razorpay.com/docs/payments/payment-links/upi · https://razorpay.com/pricing/ · https://razorpay.com/docs/payments/whatsapp |
| Cashfree | **Yes — docs: "KYC not required for simulated testing", instant** | UPI intent/collect via PG APIs in sandbox | 1.95% incl. UPI; 0% offer for new signups up to ₹20L GMV till 31-Mar-2027 | Payment links shareable on WA; native Meta payment integration [unverified] | https://www.cashfree.com/docs/payments/quickstart-guide · https://www.cashfree.com/payment-gateway-charges/ |
| PhonePe PG | UAT sandbox creds via Business dashboard "Test Mode" toggle; needs a PhonePe Business account (business details; KYC for prod) | UAT sandbox simulates success/failure/pending | 1.99% standard, shown struck-through as "Free*" promo | Not in Meta's supported-PG list [unverified] | https://developer.phonepe.com/payment-gateway/uat-testing-go-live/uat-sandbox · https://www.phonepe.com/business-solutions/payment-gateway/pricing/ |
| PayU | **Yes — test key/salt immediately, "ignore KYC for test account"** | **UPI in-app and UPI intent NOT available in test mode** (test VPA collect only) — kills it for UPI demos | ~2% [unverified — not clearly published] | PayU is among Meta's supported PGs for native WA payments [unverified] | https://docs.payu.in/docs/test-integration · https://docs.payu.in/docs/faqs-for-dashboard |
| Setu UPI (UMAP) | Sandbox `uat.setu.co`; keys "pre-seeded the moment you create an app" in The Bridge dashboard | DeepLinks, collect, mandates, QR, Infinite VPA | Not published (enterprise contract) | Has a "WhatsApp Collect" product | https://docs.setu.co/payments/umap/api-overview · https://docs.setu.co/api-references |

- **UPI 123PAY:** no self-serve sandbox exists anywhere. It runs on bank IVRs / ToneTag VoiceSe under sponsor-bank partnerships (e.g. Tata Capital rollout). Prototype must simulate it. https://www.tatacapital.com/content/dam/tata-capital/pdf/media-center/press-release/2023/Press%20release%20Tata%20Capital%20UPI%20123%202604.pdf · https://tonetag.com/ekosha/
- **UPI MDR status (Nov 2026):** NPCI framework approved Sep-2026 — 0.4% MDR on P2M txns >₹2,000 (cap ₹300); P2P, P2M ≤₹2,000 and small-merchant QR receipts stay free; rollout deferred post-Diwali, date still unannounced; M2M may get a flat ₹5 instead. PGs charge their own ~2% platform fee regardless of MDR. https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2310586 · https://www.npci.org.in/uploads/UPI_MDR_on_Select_Merchant_Transactions_Shall_be_Implemented_Post_Diwali_4c9cdd77d5.pdf · https://www.livemint.com/money/upi-fee-shock-eased-b2b-transactions-may-now-attract-just-5-charge-under-revised-mdr-plan-11795088050504.html

## 3. BBPS bill fetch + pay

| Provider | Sandbox | Signup needs | Cost | Notes |
|---|---|---|---|---|
| Setu BillPay | Yes (`sandbox-coudc.setu.co`) | API keys via onboarding@setu.co; BBPS agent setup needs business details, NPCI approval of screens, submitted test cases | Not published | Full agent model (fetch/pay/dispute, UPMS). Heaviest onboarding. https://docs.setu.co/payments/billpay/api-integration/quickstart |
| Cashfree BBPS COU | Yes — docs publish sandbox agent IDs + test billers | Contact account manager to set up; creds then in Merchant Dashboard | Not published | Prefund/postfund wallet options; sync or async responses. https://www.cashfree.com/docs/api-reference/other-apis/bbps-cou/overview · .../data-to-test-integration |
| **Eko (EPS)** | **Yes — self-serve: mobile OTP signup → UAT creds immediately; free mock server `npx @ekoindia/eps-mock-server`** | Mobile + OTP for UAT; org KYC (PAN/address/business docs) only for production | Sandbox free; production: ₹20,000 one-time setup per payments-API family (25% off promo) — BBPS itself pays the *agent a commission* per bill (e.g. ~₹1.20 electricity) | Cheapest paperwork to a working BBPS sandbox. Wallet-funded agent model. https://eps.eko.in/signup · https://eps.eko.in/pricing · https://eps.eko.in/products/bbps-api |
| NPCI direct (BBPCU/COU) | UAT only for onboarded entities | Must be/become an Operating Unit via sponsor bank — regulated entity, months | n/a | Not a realistic path for a prototype. https://www.bharatbillpay.com |

## 4. Genuinely free options

- **DigiLocker:** API Setu sandbox — zero signup, free, but a canned-data playground only (sandbox.api-setu.in). For code-level integration today: IDfy SelfServe or Veriqos free trials (vendor-gated but no company docs).
- **UPI:** Razorpay test mode and Cashfree sandbox — both free, no KYC, unlimited. NPCI offers **no** public UPI sandbox; UPI rail access is always via a PSP/sponsor bank.
- **BBPS:** Eko UAT — free after mobile-OTP signup, plus a runnable local mock server. Setu/Cashfree BBPS sandboxes exist but are sales/account-manager gated.

## Recommendation

**Cheapest setup today (no company, least paperwork):**
1. DigiLocker → API Setu sandbox to see real request/response shapes; IDfy SelfServe trial for an actual API key. Keep the prototype's SIMULATED adapter; nothing here is worth sales cycles yet.
2. UPI → **Razorpay test mode** (richest test coverage: intent + payment links) or **Cashfree sandbox** (equally KYC-free; 0% fee offer live). Avoid PayU for UPI demos — no UPI intent in test mode.
3. BBPS → **Eko UAT** — the only self-serve real BBPS API found; its local mock server also suits CI.

**What changes going live:** register an entity (all live creds need business PAN; Razorpay/Cashfree now do CKYC/video KYC); UPI moves to a live PG key at ~2% platform fee (UPI ≤₹2,000 stays MDR-free under the pending NPCI framework); BBPS moves to Eko production (~₹20k setup, org KYC, prepaid wallet — agent earns per-bill commission) or Setu for enterprise volumes; DigiLocker moves to a reseller (Setu/Cashfree/IDfy — per-call pricing, sales-quoted) or API Setu requester direct, which adds committee approval, quarterly reports and an STQC audit.
