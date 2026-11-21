import type { Call, PaymentStatus } from './types'

export type StepKey = 'greeting' | 'number' | 'bill' | 'amount' | 'upi' | 'result'
export type StepStatus = 'done' | 'current' | 'todo' | 'failed'

export const STEP_LABELS: Record<StepKey, string> = {
  greeting: 'Greeting',
  number: 'Number confirmed',
  bill: 'Bill',
  amount: 'Amount confirmed',
  upi: 'UPI 123PAY',
  result: 'Result',
}

const KEYS = Object.keys(STEP_LABELS) as StepKey[]
const AFTER_NUMBER = ['fetching_bill', 'confirming_amount', 'paying']
const TERMINAL = ['done', 'handed_off', 'ended']

export function computeSteps(call: Call): { key: StepKey; label: string; status: StepStatus }[] {
  const { bill, payment } = call
  const ended = TERMINAL.includes(call.state) || !!call.ended_at
  const upiDone = !!payment && payment.status !== 'pending'
  const done: Record<StepKey, boolean> = {
    greeting: call.state !== 'greeting' || ended,
    number: !!bill || !!payment || AFTER_NUMBER.includes(call.state),
    bill: !!bill || !!payment,
    amount: !!bill?.amount_confirmed || !!payment,
    upi: upiDone,
    result: payment?.status === 'confirmed',
  }
  let currentTaken = ended
  return KEYS.map((key) => {
    let status: StepStatus = done[key] ? 'done' : 'todo'
    if (key === 'result' && payment?.status === 'failed') status = 'failed'
    if (status === 'todo' && !currentTaken) {
      status = 'current'
      currentTaken = true
    }
    return { key, label: STEP_LABELS[key], status }
  })
}

export const showSimulated = (call: Call): boolean => !!(call.bill?.simulated || call.payment?.simulated)

const PAY_OUTCOME: Record<string, PaymentStatus> = {
  paid: 'confirmed', payment_failed: 'failed', payment_pending: 'pending',
}

export function billConfirmation(call: Call): { text: string; ok: boolean } | null {
  const { bill } = call
  if (!bill) return null
  if (bill.amount_confirmed) return { text: '✓ Amount confirmed by citizen', ok: true }
  if (bill.amount_inr === 0) return { text: 'Nothing to pay', ok: false }
  if (TERMINAL.includes(call.state) || call.ended_at) return { text: 'Not confirmed', ok: false }
  return { text: 'Awaiting citizen confirmation', ok: false }
}

export function endOfCall(call: Call): string | null {
  const o = call.outcome
  if (!o) return null
  const text = o.replace(/_/g, ' ')
  const implied = PAY_OUTCOME[o]
  if (!implied) return `At end of call: ${text}`
  if (!call.payment) return null
  return `At end of call: ${text}${call.payment.status !== implied ? ` (payment is now ${call.payment.status})` : ''}`
}
