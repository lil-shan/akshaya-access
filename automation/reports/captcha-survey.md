# Captcha survey (2026-11-21)

Headless Chromium, public landing/login pages only, nothing clicked or entered. Detection is a keyword scan of the DOM and visible text of the landing page, so **most entries are UNCERTAIN**: many portals show the login form only after a click (not done), or load it late. Screenshots in `reports/captcha/`. Script: `scripts/captcha_survey.py`.

| Portal | URL | Reachable | Captcha seen | Login method visible |
|---|---|---|---|---|
| edistrict-kerala | https://edistrict.kerala.gov.in/ | yes (HTTP 200) | none visible | none visible |
| ksmart | https://ksmart.lsgkerala.gov.in/ui/web-portal | yes (HTTP 200) | none visible | none visible |
| kseb-quickpay | https://wss.kseb.in/selfservices/quickpay | yes (HTTP 200) | image (captcha text/element in DOM) | none visible |
| kwa-epay | https://epay.kwa.kerala.gov.in/ | yes (HTTP 200) | reCAPTCHA, audio option? | none visible |
| civil-supplies-ecitizen | https://ecitizen.civilsupplieskerala.gov.in/ | yes (HTTP 200) | none visible | none visible |
| voters-eci | https://voters.eci.gov.in/login | yes (HTTP 200) | image (captcha text/element in DOM) | none visible |
| pan-protean | https://www.protean-tinpan.com/ | yes (HTTP 200) | reCAPTCHA | Aadhaar OTP |
| pan-incometax-epan | https://eportal.incometax.gov.in/iec/foservices/#/pre-login/instant-e-pan | no: Page.goto: Timeout 45000ms exceeded. | n/a | n/a |
| passport-seva | https://services1.passportindia.gov.in/forms/ | yes (HTTP 200) | reCAPTCHA | none visible |
| epfo-member | https://unifiedportal-mem.epfindia.gov.in/memberinterface/ | yes (HTTP 500) | none visible | none visible |
| kerala-police-thuna | https://thuna.keralapolice.gov.in/ | yes (HTTP 200) | image (captcha text/element in DOM) | none visible |

## Notes

- `none visible` means not found on the landing page, NOT that the login has no captcha. Real login pages for e-District, K-SMART, civil supplies, EPFO, Thuna are behind a click or tab. UNCERTAIN.
- `image (captcha text/element in DOM)`: the word 'captcha' appears with no reCAPTCHA/hCaptcha marker; assumed a text-image captcha. UNCERTAIN, verify from the screenshot.
- `audio option?`: a 'listen' or 'audio' word appeared near captcha text; for reCAPTCHA it is the standard audio challenge (which Google often withholds from automated browsers). UNCERTAIN.
- Incometax e-PAN (eportal.incometax.gov.in) timed out headless (heavy SPA / bot filtering). EPFO member returned HTTP 500 at this URL. Passport Seva, PAN and others: login method detection is weak (landing pages).
- First-pass URLs for K-SMART, KSEB, Protean and Passport were wrong (DNS failure / 404) and were corrected in the final run.
- Takeaway for the product: assume an image captcha everywhere, reCAPTCHA on KWA, Protean and Passport Seva (cannot be relayed as an image to the citizen; portal is 'later'), and OTP on most. Re-survey by hand before building any dry-run.
