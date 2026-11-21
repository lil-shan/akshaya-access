# Captcha survey (2026-11-21, round 2)

Method: headless Chromium (desktop Chrome UA), read-only. Open landing page, click ONE visible navigation link by text (Login / Sign In / Register / Apply), then scan that page's DOM. Nothing typed, no OTP or submit pressed. Script: `scripts/captcha_survey2.py`; raw rows `reports/captcha-survey2.json`; screenshots `reports/captcha/<portal>-login.png` (and round-1 `<portal>.png`).
Caveat: detection is a DOM keyword scan. "audio option present" means the words audio/listen/speak appear on the page, NOT that an audio challenge was heard. Marked `(verify)` where that is the only evidence.

| Portal | Page reached | Captcha | Login method | Phone-relayable? |
|---|---|---|---|---|
| edistrict-kerala | edportalsignin.jsp (Sign In) | image, no audio seen | username/password (OTP not shown) | whatsapp |
| ksmart | landing (Register click stayed on SPA page) | none seen; login not reached | not reached | unknown (SPA, needs manual look) |
| kseb-quickpay | quickpay + complaint page | image, no audio seen | none (anonymous payment/complaint) | whatsapp |
| kwa-epay | /register | reCAPTCHA (+ standard audio challenge) | phone registration | no |
| civil-supplies-ecitizen | landing, no nav link matched | none seen; login not reached | not reached | unknown |
| voters-eci | /login | image + audio option present (verify) | mobile OTP | yes (verify) |
| pan-protean | landing: reCAPTCHA; TIN-FC login page: none | reCAPTCHA on public PAN pages | Aadhaar (landing), username/password (TIN-FC) | no |
| pan-incometax-epan | eportal.incometax.gov.in login (URL fixed: start at www.incometax.gov.in/iec/foportal/) | none on first step (captcha may appear after user ID, not tested) | PAN/Aadhaar user ID then password | unknown (likely yes) |
| passport-seva | /forms/PreLogin | reCAPTCHA | none shown pre-login | no |
| epfo-member | /memberinterface/ (URL fixed: base domain; earlier 500 was the wrong path) | image + audio option present (verify) | UAN + password, Aadhaar-linked | yes (verify) |
| kerala-police-thuna | landing login | image + audio option present (verify) | mobile OTP and username/password | yes (verify) |

## Takeaways
- reCAPTCHA (KWA, Protean, Passport Seva): not relayable, keep as later / manual.
- Image captcha with no audio found (e-District, KSEB): relay the image over WhatsApp, not voice.
- Voters portal, EPFO, Thuna appear to offer audio captchas, but this must be confirmed by hand before building a voice relay.
- K-SMART, civil supplies, Income Tax e-PAN: the real challenge appears after navigation or typing, which this read-only survey cannot do. Check manually.
- Fixed URLs: EPFO (base domain, then Sign in), e-PAN (income tax home, then Login; the direct pre-login SPA URL times out). Login links on EPFO/Thuna/Voters stayed on the same URL (modals/SPA).
