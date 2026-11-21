# Research 1: Voice / language stack & costs (Opus agent, 2026-11-21)

## Headline
The deck's ₹2,009 matches Sarvam's pay-as-you-go card exactly (₹3.50/min agent, ₹0.20 per 30s telephony pulse, ₹59/number/30 days) but omits GST, per-call rounding, test runs and the WhatsApp channel. Realistic pilot: **~₹3,000–3,500 + WhatsApp BSP fee, excl. hosting.**

## Sarvam AI
- **Voice Agents** (ex-Samvaad, renamed Aug 2026): managed STT+LLM+TTS at one per-minute price; 11 Indian languages incl. ml/hi/ta/bn/or; code-mixing; external tool calls; India-hosted data; phone + web GA. **WhatsApp voice + text agents are enterprise-only.** https://docs.sarvam.ai/voice-agents/overview.md
- Pricing: ₹3.50/min PAYG (₹3.00 Business), 60s pulses, unanswered free, 4 concurrent on PAYG, ₹2/simulation. Telephony: Sarvam/Vobiz or BYO (Exotel, Smartflo, Plivo, Twilio…). https://www.sarvam.ai/products/voice-agents/pricing
- **Saaras v4 STT**: default; codemix/translit modes; 8 kHz telephony-optimised; WebSocket streaming; spoken numbers → digits. No published Malayalam WER. ₹0.49/min.
- **Bulbul v4 Flash TTS**: Malayalam, 8 kHz, streaming, no SSML, pronunciation dictionary. ₹2/1k chars.
- Sarvam 105B LLM ₹10/₹25 per M tokens; translation ₹2/1k chars; ₹100 free credit. https://www.sarvam.ai/api-pricing
- Govt deals: Maharashtra ₹11.26 cr (voice + WhatsApp outreach); UIDAI voice partnership (PIB). No Kerala deal found.

## Smallest.ai
- Pulse STT: Malayalam streaming only (India region, June 2026), not batch.
- Lightning TTS v3.1 lists Malayalam, ~200 ms TTFB; **v3.1 retires 30 Nov 2026**.
- Atoms agents $0.09–0.21/min; Exotel SIP guide exists. Malayalam end-to-end in Atoms unverified.
- Verdict: secondary/fallback option, not primary.

## Others
Exotel lists Malayalam as Alpha (recommends Azure/Sarvam STT, Google/Sarvam TTS). Google Chirp 3 Malayalam = Preview. Deepgram Nova-3 monolingual Malayalam. ElevenLabs Malayalam only in v3 (not low-latency). AI4Bharat IndicConformer/IndicTrans2 MIT, self-host. Bhashini production terms unclear.

## Telephony
Plivo ₹0.38/min, number ₹200/mo, streaming included, India entity + KYC + media in India. Exotel plans ₹9,999+/AgentStream on request. Avoid Twilio for domestic India. **TRAI TCCCPR 3rd Amendment (Sept 2026)**: AI-voice calls = A2P, must be declared, termination charge unless 140/1600/1601 series. **Inbound-only is the low-risk design.**

## Orchestration
Pipecat: native Sarvam + Smallest + Exotel/Plivo connectors; Sarvam publishes Exotel+Pipecat guide. LiveKit: Sarvam plugin, no Smallest. Vapi: custom providers.

## WhatsApp
Utility/auth ≈ ₹0.115, marketing ≈ ₹0.86. **From 1 Oct 2026 service messages: 1,000 free/month/number then ≈ ₹0.115.** INR billing by 31 Dec 2026. User-initiated WhatsApp calls free to business. Payments via `order_details` (BillDesk, Razorpay, PayU, Zaakpay). WhatsApp native BBPS bill pay launched 3 Sep 2026.

## Corrected pilot (500 min / 100 inbound calls)
| Item | ₹ |
|---|---|
| Sarvam minutes (rounded) | 1,750–1,850 |
| Telephony | 200–220 |
| Number | 59 |
| ~100 test simulations | 200 |
| GST 18% (assumed) | ~400–420 |
| **Phone total** | **~2,600–2,750** |
| WhatsApp STT/TTS for 500 voice notes | 250–600 |
| WhatsApp messages | 0–50 |
| BSP fee | varies |

## Recommended
- Phone: Sarvam Voice Agents, inbound, Sarvam/Vobiz or Exotel telephony.
- WhatsApp: own bot on Meta Cloud API + Saaras v4 + Bulbul v4 Flash + Sarvam 105B.
- Payment: UPI `order_details` or handoff to WhatsApp BBPS bill pay.
- Alternative: self-hosted Pipecat (Sarvam or Smallest) + Plivo/Exotel, one pipeline for both channels; more control, more engineering.

## Not verified
Independent Malayalam WER/latency; Smallest Atoms Malayalam end-to-end + INR pricing; Exotel AgentStream price; Twilio India; Bhashini terms; WhatsApp service rate (₹0.115 vs ₹0.145); KSEB on WhatsApp bill pay; TRAI series details; GST rate; DLT for SMS payment links; LiveKit Sarvam STT support; **DTMF keypad support in Sarvam Voice Agents (not checked)**.
