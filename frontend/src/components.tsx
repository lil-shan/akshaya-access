import { useEffect, useRef, useState } from 'react'
import type { Call, CallEvent, Handoff, Payment, Bill } from './types'
import { billConfirmation, computeSteps, endOfCall, showSimulated } from './steps'
import { api } from './api'

const time = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '')
const inr = (n: number) => `₹${n.toLocaleString('en-IN')}`
const label = (s: string) => s.replace(/_/g, ' ')

export const SimBadge = () => <span className="sim-badge" title="Simulated integration — no real money or real KSEB data">SIMULATED</span>

export function CallList({ calls, selectedId, pinned, onSelect, onFollow }: {
  calls: Call[]; selectedId: string | null; pinned: boolean; onSelect: (id: string) => void; onFollow: () => void
}) {
  return (
    <section className="panel">
      <h2>Calls</h2>
      {pinned && <button className="link" onClick={onFollow}>Follow newest active call</button>}
      {calls.length === 0 && <p className="muted">No calls yet. Waiting for a call…</p>}
      <ul className="calls">
        {calls.map((c) => (
          <li key={c.call_id}>
            <button className={`call-item${c.call_id === selectedId ? ' selected' : ''}`} onClick={() => onSelect(c.call_id)}>
              <span className="phone">{c.caller_phone_masked}</span>
              <span className={`state state-${c.ended_at ? 'ended' : 'live'}`}>{c.ended_at ? 'ended' : 'live'} · {label(c.state)}</span>
              <span className="muted small">{time(c.started_at)}{endOfCall(c) ? ` · ${endOfCall(c)!.replace('At end of call', 'at end')}` : ''}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Bubble({ e }: { e: CallEvent }) {
  if (e.type === 'state') return <div className="state-chip">{label(e.text)}</div>
  const agent = e.type === 'agent_said'
  return (
    <div className={`bubble ${agent ? 'agent' : 'citizen'}`}>
      <div className="who">{agent ? 'Agent' : 'Citizen'} · {time(e.at)}</div>
      <div className="ml" lang="ml">{e.text}</div>
      {e.text_en && <div className="en">{e.text_en}</div>}
    </div>
  )
}

export function Transcript({ call }: { call: Call | null }) {
  const end = useRef<HTMLDivElement>(null)
  const n = call?.events.length ?? 0
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [n, call?.call_id])
  return (
    <section className="panel transcript">
      <h2>Live transcript {call && <span className="muted small">· {call.channel}</span>}</h2>
      <div className="bubbles">
        {!call && <p className="muted">Select or wait for a call.</p>}
        {call?.events.map((e) => <Bubble key={e.seq} e={e} />)}
        <div ref={end} />
      </div>
    </section>
  )
}

const MARK = { done: '✓', current: '●', todo: '', failed: '✗' }

export function StepTracker({ call }: { call: Call }) {
  return (
    <ol className="steps">
      {computeSteps(call).map((s) => (
        <li key={s.key} className={`step ${s.status}`}>
          <span className="dot">{MARK[s.status]}</span>
          {s.label}
        </li>
      ))}
    </ol>
  )
}

export function BillCard({ call }: { call: Call }) {
  const bill: Bill | null | undefined = call.bill
  const conf = billConfirmation(call)
  return (
    <div className="card">
      <h3>Bill {bill?.simulated && <SimBadge />}</h3>
      {!bill ? <p className="muted">Not fetched yet</p> : (
        <>
          <div className="ml big" lang="ml">{bill.customer_name}</div>
          {bill.customer_name_en && <div className="muted">{bill.customer_name_en}</div>}
          <div className="amount">{inr(bill.amount_inr)}</div>
          <div className="muted small">Consumer no. {bill.consumer_number}</div>
          <div className="muted small">Due {bill.due_date ?? '—'}</div>
          {conf && <div className={`flag ${conf.ok ? 'ok' : ''}`}>{conf.text}</div>}
        </>
      )}
    </div>
  )
}

export function PaymentCard({ payment, onChanged }: { payment?: Payment | null; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const complete = async (outcome: 'confirmed' | 'failed') => {
    if (!payment) return
    setBusy(true); setErr('')
    try { await api.completePayment(payment.payment_id, outcome); onChanged() }
    catch (e) { setErr(`Could not update payment (${(e as Error).message})`) }
    finally { setBusy(false) }
  }
  return (
    <div className="card">
      <h3>Payment · UPI 123PAY {payment?.simulated && <SimBadge />}</h3>
      {!payment ? <p className="muted">Not started</p> : (
        <>
          <div className={`pay-status ${payment.status}`}>{payment.status}</div>
          <div>{inr(payment.amount_inr)}</div>
          {payment.status === 'confirmed' && payment.reference && <div className="muted small">Reference {payment.reference}</div>}
          {payment.status === 'pending' && (
            <div className="demo">
              <div className="demo-label">Demo controls — stand in for the bank</div>
              <div className="row">
                <button className="btn good" disabled={busy} onClick={() => complete('confirmed')}>Bank confirms</button>
                <button className="btn bad" disabled={busy} onClick={() => complete('failed')}>Bank declines</button>
              </div>
              {err && <div className="err">{err}</div>}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export function HandoffBanner({ handoff }: { handoff?: Handoff | null }) {
  if (!handoff) return null
  return (
    <div className="handoff">
      <strong>Handed off to a human</strong> · {label(handoff.reason)} · case number {handoff.case_number} ({handoff.status})
      {handoff.note && <div className="small">{handoff.note}</div>}
    </div>
  )
}

export function RightPanel({ call, onChanged }: { call: Call | null; onChanged: () => void }) {
  if (!call) return <section className="panel"><h2>Case</h2><p className="muted">No call selected.</p></section>
  return (
    <section className="panel">
      <h2>Case {showSimulated(call) && <SimBadge />}</h2>
      <HandoffBanner handoff={call.handoff} />
      <StepTracker call={call} />
      <BillCard call={call} />
      <PaymentCard payment={call.payment} onChanged={onChanged} />
      {endOfCall(call) && <div className="muted small">{endOfCall(call)}</div>}
    </section>
  )
}
