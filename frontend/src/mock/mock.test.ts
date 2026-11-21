import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { computeSteps, showSimulated } from '../steps'

async function load() {
  vi.resetModules()
  return (await import('./mock')).mockApi
}

describe('mock scripted call', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('plays through to a pending SIMULATED payment, then bank confirms', async () => {
    const api = await load()
    const [first] = await api.listCalls()
    expect(first.state).toBe('greeting')
    expect(first.caller_phone_masked).toBe('******4321')

    vi.advanceTimersByTime(20_000)
    const c = await api.getCall('mock-call-1')
    expect(c.payment?.status).toBe('pending')
    expect(c.bill?.amount_inr).toBe(640)
    expect(c.bill?.amount_confirmed).toBe(true)
    expect(showSimulated(c)).toBe(true)
    expect(computeSteps(c).find((s) => s.status === 'current')?.key).toBe('upi')

    await api.completePayment('mock-pay-1', 'confirmed')
    const done = await api.getCall('mock-call-1')
    expect(done.payment?.status).toBe('confirmed')
    expect(done.payment?.reference).toBeTruthy()
    expect(done.outcome).toBe('paid')
    expect(done.state).toBe('ended')
    expect(done.ended_at).toBeTruthy()
    expect(computeSteps(done).every((s) => s.status === 'done')).toBe(true)
    await expect(api.completePayment('mock-pay-1', 'failed')).rejects.toThrow('409')
    await expect(api.completePayment('other', 'failed')).rejects.toThrow('404')
  })

  it('opens with AI identity and the no-OTP/PIN promise; citizen lines are normalized', async () => {
    const api = await load()
    vi.advanceTimersByTime(20_000)
    const c = await api.getCall('mock-call-1')
    const opening = c.events.find((e) => e.type === 'agent_said')!
    expect(opening.text_en).toMatch(/AI assistant, not a human/)
    expect(opening.text_en).toMatch(/never ask for your OTP, UPI PIN or Aadhaar/)
    const citizen = c.events.filter((e) => e.type === 'citizen_said').map((e) => e.text_en)
    expect(citizen).toEqual(['[consumer number 1155432100987]', '[yes]', '[yes]'])
    const ask = c.events.filter((e) => e.type === 'agent_said' && /shall I start the payment/.test(e.text_en ?? ''))
    expect(ask).toHaveLength(1)
  })

  it('bank declines -> failed, no reference', async () => {
    const api = await load()
    vi.advanceTimersByTime(20_000)
    await api.completePayment('mock-pay-1', 'failed')
    const c = await api.getCall('mock-call-1')
    expect(c.payment?.status).toBe('failed')
    expect(c.payment?.reference).toBeNull()
    expect(c.outcome).toBe('payment_failed')
  })
})
