# thuna_lost_property — thuna.keralapolice.gov.in (lost property). Read-only survey 2026-11-21
Legend: [seen] observed (rendered DOM or the portal's public JS bundle `snapshots/14.*.chunk.js`); [assumed] not visible without logging in.
Snapshots: `snapshots/home.html|png`, JS chunk with the English UI strings for the lost-property form.
Login was NOT opened (the "Login" button was not clicked), so the login panel was read from the JS bundle, not rendered.

## Login [seen in bundle]
1. Home page: header buttons `button.signInbutton` ("Login", two copies, one hidden on desktop), `button.signupbutton` ("Create Account"), language button.
2. Login form (Formik): `userName` (mobile, 10-15 digits), **`password`** (8-24 chars, letters+digits+symbol), `captcha` (exactly 6 chars), `otp` (6 digits; shown only when the portal requires 2-step).
   **Finding: Thuna login needs a PASSWORD in addition to mobile + captcha (+ OTP).** Contract v1.2 says "mobile-OTP login": that is only the forgot-password/registration route.
   The worker asks the password at runtime via job_prompts kind='field' (used once, nulled). Decision needed from the contract owner (EPFO password flows were excluded).
3. **Audio captcha: NO [seen in bundle]**: only an image with "Reload image" (`pe-7s-refresh-2` button); no audio control or endpoint in any chunk. Image captcha relay only.
4. API names [seen]: `login`, `loginOtp`, `validateOTPlogin`, `resendOTPLogin`, `logout`.
## Lost property [seen as UI strings; page order/selectors assumed]
Services menu "Lost Property" -> "New Lost Property Request / Register for Lost Property Request" -> tab "Lost Property Details": "Is lost date known?", "Lost Date" or
"Lost Date From/To", "Description of Lost", "Lost Details" -> "Property Details" ("Add Property Details": Property Category, Property Type, then category-specific:
Item Name, Item Number, IMEI Number, Serial Number, Place of Issue, Date of Issue, Passport No., Bank/Card No., Vehicle/Engine/Chassis No...) -> "Attach file, if any" ->
tab **"Preview & Submit"** -> button **"Submit Lost Property Request"** (success: "Lost Property Request submitted successfully."). Complainant details presumably from the account profile.
The dry run stops BEFORE the "Preview & Submit" control (it matches the denylist), screenshots the filled form, logs out (`#logout` [assumed]).
Aadhaar: if the portal asks for it, the run stops (citizen enters it on the portal).
