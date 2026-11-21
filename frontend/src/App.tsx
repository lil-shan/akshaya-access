import { useEffect, useRef, useState } from 'react'
import { api, BACKEND_URL, USE_MOCK } from './api'
import type { Call } from './types'
import { CallList, RightPanel, Transcript } from './components'

function usePoll<T>(fn: () => Promise<T>, key: string, ms = 1000) {
  const [state, setState] = useState<{ data: T | null; error: boolean }>({ data: null, error: false })
  const fnRef = useRef(fn)
  fnRef.current = fn
  const runRef = useRef<() => Promise<void>>(async () => {})
  useEffect(() => {
    let alive = true
    let timer: number
    const run = async () => {
      try {
        const data = await fnRef.current()
        if (alive) setState({ data, error: false })
      } catch {
        if (alive) setState((s) => ({ ...s, error: true }))
      }
    }
    runRef.current = run
    const loop = async () => {
      await run()
      if (alive) timer = window.setTimeout(loop, ms)
    }
    setState({ data: null, error: false })
    loop()
    return () => { alive = false; clearTimeout(timer) }
  }, [key, ms])
  return { ...state, refresh: () => runRef.current() }
}

export default function App() {
  const [pinnedId, setPinnedId] = useState<string | null>(null)
  const list = usePoll<Call[]>(() => api.listCalls(), 'list')
  const calls = list.data ?? []
  const newestActive = calls.find((c) => !c.ended_at) ?? calls[0]
  const selectedId = pinnedId ?? newestActive?.call_id ?? null
  const detail = usePoll<Call | null>(() => (selectedId ? api.getCall(selectedId) : Promise.resolve(null)), selectedId ?? '')
  const call = detail.data?.call_id === selectedId ? detail.data : null
  const offline = list.error || detail.error

  return (
    <div className="app">
      <header>
        <h1>Akshaya-Access <span className="muted">· live call</span></h1>
        <div className="tags">
          {USE_MOCK && <span className="tag">MOCK DATA</span>}
          <span className="tag muted">{USE_MOCK ? 'no backend' : BACKEND_URL}</span>
        </div>
      </header>
      {offline && <div className="offline">Backend unreachable{USE_MOCK ? '' : ` at ${BACKEND_URL}`} — retrying every second…</div>}
      <main>
        <CallList calls={calls} selectedId={selectedId} pinned={pinnedId !== null} onSelect={setPinnedId} onFollow={() => setPinnedId(null)} />
        <Transcript call={call} />
        <RightPanel call={call} onChanged={() => { detail.refresh(); list.refresh() }} />
      </main>
    </div>
  )
}
