# 06 — Research: which citizen services can be filed by Playwright for a caller

You are doing web research, not code review. Write `reviews/research-06-services.md`. Cite an official URL for every
claim; mark anything you could not verify as **[unverified]**. Today is 2026-11-21.

Product: citizens in Kerala call us (inbound only); an AI agent collects the details by voice in Malayalam; Playwright
fills the official web form on the citizen's behalf; the citizen gives us any OTP the portal sends during the call; a human
operator on our side types any captcha (we do NOT automate captchas); the UPI PIN is always entered by the citizen with
their bank. Government fees are paid on the portal's own payment page.

For ~15 candidate services, starting with these, find:
e-District Kerala (income, nativity, residence, community, relationship, one-and-the-same certificates),
K-SMART (birth/death certificate, building tax), KSEB and KWA bill pay, ration card services (civil supplies),
PMJJBY / PMSBY claim forms (PDF), voter Form 6/8 (ECI), PAN (Protean / e-PAN), passport fresh/renewal (Passport Seva), EPFO claim.

Table columns: Service | Portal URL | Who logs in (citizen account / Akshaya-CSC operator account / no login) |
Login method (mobile OTP / Aadhaar OTP / password) | Captcha? | Fields required | Documents to upload |
Fee + how paid | In-person/biometric step? | Tier: 1 = fill official PDF form, 2 = Playwright on citizen login with OTP,
3 = API/sandbox, 4 = not automatable | Can it be demoed end to end with DUMMY data without filing a real application? (yes/no + how)

Then: a ranked list "build first" (works 100% with dummy data) vs "build later" (needs a real citizen / dry-run only).
Include for each Tier-2 portal whether its terms of use forbid automated access, if stated.
Keep the report under 200 lines.
