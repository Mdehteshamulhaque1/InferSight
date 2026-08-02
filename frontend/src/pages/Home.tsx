import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../app/providers/AuthContext'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import { Dropzone } from '../components/ui/Dropzone'
import {
  AnalysisChecklist,
  AnalysisReport,
  demoCSV,
} from '../components/features/analysis/AnalysisReport'
import { IconArrowRight, IconSparkles } from '../components/ui/icons'
import type { AnalysisSummary } from '../types'

interface Msg {
  role: 'user' | 'assistant'
  text: string
  followups?: string[]
  file?: boolean
  error?: boolean
  summary?: AnalysisSummary
}

export function Home() {
  const { user } = useAuth()
  usePageTitle('Home')
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [importing, setImporting] = useState(false)
  const [datasetId, setDatasetId] = useState<number | null>(null)
  const [summaryDone, setSummaryDone] = useState(false)
  const [report, setReport] = useState<AnalysisSummary | null>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  const datasets = useAsync(() => api.listDatasets(1, 5), [])
  const name = user?.full_name?.trim().split(/\s+/)[0]

  useEffect(() => {
    if (!user) return
    setMessages([
      {
        role: 'assistant',
        text: `👋 Welcome${name ? `, ${name}` : ''} to InferSight. Drop a CSV and I'll clean it, analyze it, detect anomalies, forecast, and score its health — automatically. No buttons to press.`,
        followups: [
          'Summarize my latest dataset',
          'What anomalies are active right now?',
          'What should I improve?',
        ],
      },
    ])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user])

  useEffect(() => {
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, busy, importing])

  async function ask(text?: string) {
    const q = (text ?? input).trim()
    if (!q || busy || importing) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }])
    setBusy(true)
    try {
      const out = await api.chat(q, datasetId)
      setMessages((m) => [...m, { role: 'assistant', text: out.reply, followups: out.followups }])
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: e instanceof Error ? e.message : 'Sorry — I could not reach the engine.',
          error: true,
        },
      ])
    } finally {
      setBusy(false)
    }
  }

  async function runAnalysis(f: File) {
    setImporting(true)
    setMessages((m) => [...m, { role: 'user', text: f.name, file: true }])
    try {
      const res = await api.autoImport(f)
      setDatasetId(res.dataset.id)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: `Imported “${res.dataset.name}” — ${res.result.inserted.toLocaleString()} point${
            res.result.inserted === 1 ? '' : 's'
          } at ${res.result.detected_granularity} granularity. Cleaning, analyzing, detecting anomalies, forecasting, and scoring health…`,
        },
      ])
      const summary = await api.summary(res.dataset.id)
      setSummaryDone(true)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: '',
          summary,
          followups: [
            'Walk me through the results',
            'Why did revenue move?',
            'Forecast next 3 months.',
            'What should I improve?',
          ],
        },
      ])
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text:
            e instanceof Error
              ? e.message
              : 'Upload failed — please check the file and try again.',
          error: true,
        },
      ])
    } finally {
      setImporting(false)
    }
  }

  function tryDemo() {
    void runAnalysis(demoCSV())
  }

  const showUpload = !importing && !busy && !summaryDone
  const hasDatasets = (datasets.data?.items ?? []).length > 0

  if (report) {
    return (
      <div className="copilot">
        <AnalysisReport summary={report} onClose={() => setReport(null)} />
      </div>
    )
  }

  return (
    <div className="copilot">
      <div className="page-head">
        <div>
          <h1>Copilot</h1>
          <p className="sub">Your data, analyzed in plain language.</p>
        </div>
      </div>

      <div className="copilot-shell">
        <div className="copilot-body" ref={bodyRef}>
          {messages.map((m, i) =>
            m.summary ? (
              <div key={i} className="copilot-card">
                <AnalysisChecklist summary={m.summary} />
                <div className="row mt-6" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <button className="btn btn-primary" onClick={() => setReport(m.summary!)}>
                    Walk me through the results <IconArrowRight size={14} />
                  </button>
                </div>
                {m.followups && m.followups.length > 0 && (
                  <div className="copilot-followups">
                    {m.followups.map((f) => (
                      <button key={f} type="button" onClick={() => void ask(f)}>
                        {f}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div key={i}>
                <div
                  className={`copilot-msg ${m.role}${m.error ? ' error' : ''}${m.file ? ' file' : ''}`}
                >
                  {m.text}
                </div>
                {m.followups && m.followups.length > 0 && !m.error && (
                  <div className="copilot-followups">
                    {m.followups.map((f) => (
                      <button key={f} type="button" onClick={() => void ask(f)}>
                        {f}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )
          )}
          {(busy || importing) && (
            <div className="copilot-msg assistant">
              <span className="typing" aria-label="Thinking">
                <i />
                <i />
                <i />
              </span>
            </div>
          )}

          {showUpload && (
            <div className="copilot-drop">
              <Dropzone
                className="wizard-dropzone"
                onFile={(f) => void runAnalysis(f)}
                title="Drop your CSV here"
                subtitle="or browse files — I’ll do the rest automatically"
              />
              {!hasDatasets && (
                <div className="row mt-6" style={{ gap: 8, justifyContent: 'center' }}>
                  <button className="btn btn-secondary btn-sm" onClick={tryDemo}>
                    <IconSparkles size={13} /> Try a sample dataset
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <form
          className="copilot-input-row"
          onSubmit={(e) => {
            e.preventDefault()
            void ask()
          }}
        >
          <input
            className="copilot-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              importing
                ? 'Analyzing your file…'
                : busy
                  ? 'Thinking…'
                  : 'Ask about your data…'
            }
            aria-label="Ask a question"
            disabled={busy || importing}
          />
          <button
            type="submit"
            className="copilot-send"
            disabled={busy || importing || !input.trim()}
            aria-label="Send"
          >
            <IconArrowRight size={16} />
          </button>
        </form>
      </div>
    </div>
  )
}
