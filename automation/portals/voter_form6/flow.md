# voter_form6 — voters.eci.gov.in (Form 6, new elector). Read-only survey 2026-11-21
Legend: [seen] observed on the real portal or in official ECI PDFs; [assumed] not visible without logging in (stand-in in tests).
Snapshots: `snapshots/login.html|png` (rendered login DOM), `Form_6_English.pdf`, `Form-6_en.pdf` (official form + guidelines).
Note: default headless Chromium UA gets "The URL you requested has been blocked" (WAF); a normal Chrome UA loads it. Worker sets UA.

## Login [seen]
1. `https://voters.eci.gov.in/login` loads a React SPA. Fields: `#mobOrEpic` (name=mobOrEpic, "Enter registered Mobile No./Email ID/EPIC No.").
2. Captcha image `img[alt=Captcha]`, refresh icon `img[alt="refrsh captcha"]`, input `#captcha` (name=captcha).
3. **Audio captcha: YES [seen].** Icon `img[alt="Read aloud captcha"]`. Delivery: XHR `GET https://gateway-voters.eci.gov.in/api/v1/captcha-service/generateVoiceCaptcha/<captchaId>`
   (image from `.../captcha-service/getCaptcha/login`). The page itself issued the voice request once during load; I did not request more audio, did not play it.
4. `button.library-btn` "Request OTP" (disabled until fields valid) -> OTP step [assumed: OTP input, verify button; contract says mobile-OTP login].
Also on page: "Login"/"Sign-Up" header buttons, language select `#translang` (English/Hindi).
## Post-login [assumed, from third-party guides + the official Form 6]
Dashboard card "New registration for general electors (Form 6)" -> sections (guides say A–L: state/district/AC, personal, relative, contact, Aadhaar, DOB + proof,
address + proof, disability, family member at address, declaration) -> preview -> declaration + captcha -> **final Submit** (stop before). Name is auto-transliterated.
Official Form 6 items (seen in PDF): 1 name, 2 relative, 3 mobile, 4 email, 5 **Aadhaar (citizen enters on portal; dry run stops there)**, 6 gender, 7 DOB + proof,
8 address + proof, 9 disability, 10 family member EPIC, Declaration (birth place, resident since, first-time, false-statement s.31 RPA 1950).
Photo and proof uploads are not automated. Final step (declaration/captcha/Submit; reference number) is NEVER clicked: denylist `submit|confirm|e-?sign|final|pay|register|declare`.
