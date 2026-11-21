# 07 — Research: cheapest/free sandbox providers for DigiLocker, UPI and bill payment

You are doing web research, not code review. Write `reviews/research-07-providers.md`. Cite official pricing/docs URLs
for every claim; mark anything unverified **[unverified]**. Today is 2026-11-21.

Need, for a small Indian team building a prototype (no registered company yet; may register later):
1. DigiLocker document fetch with citizen consent: API Setu direct (eligibility, cost, sandbox?) vs resellers
   (Setu, Cashfree, Digio, Surepass, IDfy, Signzy, HyperVerge). Sandbox availability without a company, signup needs,
   free tier, per-call price.
2. UPI payment collection for test demos: Razorpay, Cashfree, PayU, PhonePe PG, Setu UPI — test mode without KYC?
   UPI intent/QR/payment links, UPI 123PAY support, pricing (MDR on UPI), WhatsApp payment support.
3. Bharat BillPay (BBPS) bill fetch + pay sandbox: Setu, Cashfree, others — signup needs, sandbox, pricing.
4. Any genuinely free option for each (government sandboxes like API Setu sandbox, NPCI developer sandboxes).

Output: one comparison table per need, then a recommendation: the cheapest setup that gives working sandboxes for all
three today with the least paperwork, and what changes when going live. Under 150 lines.
