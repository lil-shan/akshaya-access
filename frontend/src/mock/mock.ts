import type { Call, CallEvent, Payment } from '../types'
import fixtures from './bills.json'

const bill = fixtures.bills[0]
const digits = bill.consumer_number
const ML_DIGITS = ['പൂജ്യം', 'ഒന്ന്', 'രണ്ട്', 'മൂന്ന്', 'നാല്', 'അഞ്ച്', 'ആറ്', 'ഏഴ്', 'എട്ട്', 'ഒൻപത്']
const readBack = digits.split('').map((d) => ML_DIGITS[Number(d)]).join(', ')
const readBackEn = digits.split('').join(', ')

const PAY_ID = 'mock-pay-1'
const t0 = Date.now()
const call: Call = {
  call_id: 'mock-call-1',
  caller_phone_masked: '******4321',
  channel: 'simulator',
  language: 'ml',
  state: 'greeting',
  outcome: null,
  started_at: new Date(t0).toISOString(),
  ended_at: null,
  events: [],
  bill: null,
  payment: null,
  handoff: null,
}

function push(c: Call, type: CallEvent['type'], text: string, text_en?: string) {
  c.events.push({ seq: c.events.length + 1, at: new Date().toISOString(), type, text, text_en })
}
const setState = (c: Call, s: Call['state']) => {
  c.state = s
  push(c, 'state', s)
}

const script: [number, (c: Call) => void][] = [
  [0, (c) => push(c, 'agent_said',
    'നമസ്കാരം. ഇത് അക്ഷയ ആക്സസ് ആണ്. ഞാൻ ഒരു എ.ഐ. സഹായിയാണ്, മനുഷ്യനല്ല. ഇത് ഒരു ഡെമോ ആണ്; ഇതിലെ പണമടയ്ക്കൽ സിമുലേറ്റഡ് ആണ്. ഞാൻ ഒരിക്കലും നിങ്ങളുടെ ഒ.ടി.പി., യു.പി.ഐ. പിൻ, ആധാർ നമ്പർ എന്നിവ ചോദിക്കില്ല.',
    'Hello. This is Akshaya Access. I am an AI assistant, not a human. This is a demo; the payments in it are SIMULATED, not real. I will never ask for your OTP, UPI PIN or Aadhaar number.')],
  [2500, (c) => { setState(c, 'collecting_number'); push(c, 'agent_said', 'നിങ്ങളുടെ കൺസ്യൂമർ നമ്പർ പറയൂ.', 'Please say your KSEB consumer number.') }],
  [5000, (c) => push(c, 'citizen_said', `കൺസ്യൂമർ നമ്പർ ${digits}`, `[consumer number ${digits}]`)],
  [7000, (c) => { setState(c, 'confirming_number'); push(c, 'agent_said', `ഞാൻ കേട്ട നമ്പർ: ${readBack}. ഇത് ശരിയാണോ?`, `The number I heard is: ${readBackEn}. Is this correct?`) }],
  [9500, (c) => push(c, 'citizen_said', 'അതെ', '[yes]')],
  [11000, (c) => {
    setState(c, 'fetching_bill')
    c.bill = { ...bill, biller: 'KSEB', amount_confirmed: false, simulated: true }
  }],
  [12500, (c) => { setState(c, 'confirming_amount'); push(c, 'agent_said', `ബിൽ ${bill.customer_name} എന്ന പേരിലാണ്. അടയ്ക്കേണ്ട തുക ${bill.amount_inr} രൂപ. ഈ തുക ഇപ്പോൾ അടയ്ക്കട്ടെ?`, `The bill is in the name of ${bill.customer_name_en}. The amount due is ${bill.amount_inr} rupees (SIMULATED bill). Are the name and amount correct, and shall I start the payment now?`) }],
  [15000, (c) => push(c, 'citizen_said', 'അതെ', '[yes]')],
  [16500, (c) => {
    if (c.bill) c.bill.amount_confirmed = true
    c.payment = { payment_id: PAY_ID, bill_id: bill.bill_id, method: 'UPI_123PAY', amount_inr: bill.amount_inr, status: 'pending', reference: null, simulated: true }
    setState(c, 'paying')
    push(c, 'agent_said', 'ഇനി ബാങ്ക് ചോദിക്കുമ്പോൾ യു.പി.ഐ. പിൻ ഫോണിലെ കീപാഡിൽ അമർത്തുക. പിൻ ഉറക്കെ പറയരുത്; എനിക്ക് അത് കേൾക്കാൻ കഴിയില്ല. (ഡെമോ)', 'Enter your UPI PIN on your phone\'s keypad when your bank asks. Do not say it aloud; I cannot hear it. (SIMULATED)')
  }],
]

let applied = 0
function advance() {
  const elapsed = Date.now() - t0
  while (applied < script.length && script[applied][0] <= elapsed) script[applied++][1](call)
  return structuredClone(call)
}

export const mockApi = {
  listCalls: async (): Promise<Call[]> => [advance()],
  getCall: async (id: string): Promise<Call> => {
    if (id !== call.call_id) throw new Error('404')
    return advance()
  },
  completePayment: async (id: string, outcome: 'confirmed' | 'failed'): Promise<Payment> => {
    advance()
    if (!call.payment || call.payment.payment_id !== id) throw new Error('404')
    if (call.payment.status !== 'pending') throw new Error('409')
    const ok = outcome === 'confirmed'
    call.payment.status = outcome
    call.payment.reference = ok ? 'SIM-123PAY-48213' : null
    push(call, 'agent_said',
      ok ? 'പണമടച്ചു — ബാങ്ക് സ്ഥിരീകരിച്ചു. നന്ദി!' : 'പേയ്‌മെന്റ് പരാജയപ്പെട്ടു. പണം പോയിട്ടില്ല.',
      ok ? 'Payment received — the bank confirmed it. Thank you! (SIMULATED)' : 'The payment failed. No money was taken. (SIMULATED)')
    setState(call, 'ended')
    call.outcome = ok ? 'paid' : 'payment_failed'
    call.ended_at = new Date().toISOString()
    return structuredClone(call.payment)
  },
}
