import type { Call, Payment } from './types'
import { mockApi } from './mock/mock'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === '1'
export const BACKEND_URL: string = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BACKEND_URL + path, init)
  if (!r.ok) throw new Error(`${r.status}`)
  return r.json() as Promise<T>
}

const real = {
  listCalls: () => req<Call[]>('/calls'),
  getCall: (id: string) => req<Call>(`/calls/${encodeURIComponent(id)}`),
  completePayment: (id: string, outcome: 'confirmed' | 'failed') =>
    req<Payment>(`/simulator/payments/${encodeURIComponent(id)}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ outcome }),
    }),
}

export const api = USE_MOCK ? mockApi : real
