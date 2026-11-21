import { describe, expect, it } from 'vitest'
import { billConfirmation, computeSteps, endOfCall, showSimulated } from './steps'
import type { Bill, Call, Payment } from './types'

const base: Call = {
  call_id: 'c1', caller_phone_masked: '******4321', channel: 'simulator',
  state: 'greeting', started_at: '2027-01-01T10:00:00Z', events: [],
}
const bill: Bill = {
  bill_id: 'KSEB-SIM-0001', consumer_number: '1155432100987', customer_name: 'രാജൻ കെ',
  amount_inr: 640, amount_confirmed: false, simulated: true,
}
const pay = (status: Payment['status']): Payment => ({
  payment_id: 'p1', bill_id: bill.bill_id, method: 'UPI_123PAY', amount_inr: 640,
  status, reference: status === 'confirmed' ? 'REF1' : null, simulated: true,
})
const statuses = (c: Call) => computeSteps(c).map((s) => s.status)

describe('computeSteps', () => {
  it('has the six steps in order', () => {
    expect(computeSteps(base).map((s) => s.label)).toEqual([
      'Greeting', 'Number confirmed', 'Bill', 'Amount confirmed', 'UPI 123PAY', 'Result',
    ])
  })

  it('greeting is current at the start', () => {
    expect(statuses(base)).toEqual(['current', 'todo', 'todo', 'todo', 'todo', 'todo'])
  })

  it('number is current while collecting/confirming the number', () => {
    expect(statuses({ ...base, state: 'confirming_number' })).toEqual(['done', 'current', 'todo', 'todo', 'todo', 'todo'])
  })

  it('bill fetched but amount not confirmed -> amount is current', () => {
    expect(statuses({ ...base, state: 'confirming_amount', bill })).toEqual(['done', 'done', 'done', 'current', 'todo', 'todo'])
  })

  it('pending payment -> UPI step is current, result is todo', () => {
    const c = { ...base, state: 'paying' as const, bill: { ...bill, amount_confirmed: true }, payment: pay('pending') }
    expect(statuses(c)).toEqual(['done', 'done', 'done', 'done', 'current', 'todo'])
  })

  it('confirmed payment -> everything done', () => {
    const c = { ...base, state: 'done' as const, bill: { ...bill, amount_confirmed: true }, payment: pay('confirmed') }
    expect(statuses(c)).toEqual(['done', 'done', 'done', 'done', 'done', 'done'])
  })

  it('failed payment -> result step failed', () => {
    const c = { ...base, state: 'done' as const, bill: { ...bill, amount_confirmed: true }, payment: pay('failed') }
    expect(statuses(c)).toEqual(['done', 'done', 'done', 'done', 'done', 'failed'])
  })

  it('handed off mid-call -> no current step', () => {
    expect(statuses({ ...base, state: 'handed_off' })).toEqual(['done', 'todo', 'todo', 'todo', 'todo', 'todo'])
  })
})

describe('showSimulated', () => {
  it('false with no bill or payment', () => {
    expect(showSimulated(base)).toBe(false)
  })
  it('true when the bill is simulated', () => {
    expect(showSimulated({ ...base, bill })).toBe(true)
  })
  it('true when only the payment is simulated', () => {
    expect(showSimulated({ ...base, bill: { ...bill, simulated: false }, payment: pay('pending') })).toBe(true)
  })
  it('false when neither is simulated', () => {
    expect(showSimulated({ ...base, bill: { ...bill, simulated: false }, payment: { ...pay('pending'), simulated: false } })).toBe(false)
  })
})

describe('billConfirmation (#12)', () => {
  const zero = { ...bill, amount_inr: 0 }
  it('null without a bill', () => expect(billConfirmation(base)).toBeNull())
  it('awaiting while the call is live', () => {
    expect(billConfirmation({ ...base, state: 'confirming_amount', bill })?.text).toBe('Awaiting citizen confirmation')
  })
  it('zero bill is "Nothing to pay", live or ended', () => {
    expect(billConfirmation({ ...base, state: 'fetching_bill', bill: zero })?.text).toBe('Nothing to pay')
    expect(billConfirmation({ ...base, state: 'ended', ended_at: 'x', bill: zero })?.text).toBe('Nothing to pay')
  })
  it('declined/ended without confirmation is "Not confirmed"', () => {
    expect(billConfirmation({ ...base, state: 'ended', ended_at: 'x', bill })?.text).toBe('Not confirmed')
    expect(billConfirmation({ ...base, state: 'handed_off', bill })?.text).toBe('Not confirmed')
  })
  it('confirmed amount', () => {
    expect(billConfirmation({ ...base, bill: { ...bill, amount_confirmed: true } })).toEqual({ text: '✓ Amount confirmed by citizen', ok: true })
  })
})

describe('endOfCall (#11)', () => {
  const ended = { ...base, state: 'ended' as const, ended_at: 'x' }
  it('null without an outcome', () => expect(endOfCall(ended)).toBeNull())
  it('labels the outcome as at end of call', () => {
    expect(endOfCall({ ...ended, outcome: 'nothing_due' })).toBe('At end of call: nothing due')
    expect(endOfCall({ ...ended, outcome: 'payment_pending', payment: pay('pending') })).toBe('At end of call: payment pending')
  })
  it('late confirmation: card is confirmed, end-of-call text says pending and notes the current status', () => {
    expect(endOfCall({ ...ended, outcome: 'payment_pending', payment: pay('confirmed') }))
      .toBe('At end of call: payment pending (payment is now confirmed)')
  })
  it('never shows a payment outcome with no payment', () => {
    expect(endOfCall({ ...ended, outcome: 'paid' })).toBeNull()
  })
})
