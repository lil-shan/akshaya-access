# Critique — Sonnet (2026-11-21)
1. Phone→payment handoff breaks for feature-phone users with no WhatsApp/UPI. Fix: 3 paths — (a) own WhatsApp+UPI, (b) family member pays via link to a dictated number with consent, (c) case → named Akshaya operator pays in person. Ask early "do you have WhatsApp?".
2. 95% target unfounded; 13 digits at 98%/digit ≈ 77% whole-number. Fix: December ASR bake-off (Sarvam/Smallest/Azure) with go/no-go before build week; primary path avoids dictation — bill photo OCR / lookup by mobile.
3. Business model asserted not tested; bill pay is operators' revenue; no money to pay them. Fix: interview 10 operators in December; position v1 as operator-side tool; claim packs = paid work for them.
4. Timeline unrealistic (entity, KYC, BBPS prod not before ~March; whole stack in one week). Fix: Feb = phone agent + WhatsApp bill-image flow + operator pays manually; entity/MoU in December.
5. Differentiator (claim packs) comes last. Fix: move claim-pack prep to phase 1 as primary test.
Smaller: TRAI may apply inbound; proxy/family consent flow missing; cost omits GST/BSP/payouts; opener too long.
Keep: inbound-only, no funds held, postfunded BBPS, no UPI collect, shared Tools API, code guards, no OTP/PIN/Aadhaar, handoff, KB with source/date, Pipecat fallback.
