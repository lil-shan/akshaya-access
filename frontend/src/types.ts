export type CallState =
  | 'greeting' | 'collecting_number' | 'confirming_number' | 'fetching_bill'
  | 'confirming_amount' | 'paying' | 'done' | 'handed_off' | 'ended'

export interface CallEvent {
  seq: number
  at: string
  type: 'agent_said' | 'citizen_said' | 'state'
  text: string
  text_en?: string
}

export interface Bill {
  bill_id: string
  biller?: 'KSEB'
  consumer_number: string
  customer_name: string
  customer_name_en?: string
  amount_inr: number
  due_date?: string | null
  amount_confirmed: boolean
  simulated: boolean
}

export type PaymentStatus = 'pending' | 'confirmed' | 'failed'

export interface Payment {
  payment_id: string
  bill_id: string
  method: 'UPI_123PAY'
  amount_inr: number
  status: PaymentStatus
  reference?: string | null
  simulated: boolean
}

export interface Handoff {
  case_id: string
  case_number: string
  call_id: string
  reason: string
  note?: string | null
  status: 'queued'
}

export interface Call {
  call_id: string
  caller_phone_masked: string
  channel: string
  language?: string
  state: CallState
  outcome?: string | null
  started_at: string
  ended_at?: string | null
  events: CallEvent[]
  bill?: Bill | null
  payment?: Payment | null
  handoff?: Handoff | null
}
