# Role: VOICE   (your folder: /home/shan/devin/voice)
You own the phone-call agent: telephony + speech (Sarvam: Saaras STT, Bulbul TTS, or Sarvam Voice Agents),
the Malayalam conversation script, digit-by-digit read-back and confirmation, and calling the backend Tools API
exactly as defined in contracts/. Never let OTP/PIN audio or digits be captured or logged; the UPI 123PAY step is a
handoff where the citizen enters the PIN on the keypad to the bank's IVR, not to us. Provide a text-mode simulator
so the flow can be tested without a phone line.
