import { useEffect, useState } from 'react'
import { api } from '../api'
import type { InsightOut } from '../types'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import { useToast } from '../components/ui/Toast'
import { RelatedSignalsPanel } from '../components/features/related-signals/RelatedSignalsPanel'
import { IconChevronRight, IconRefresh, IconSpark, IconTrash } from '../components/ui/icons'
import { fmtDateTime, severityClass } from '../lib/format'

interface InsightPayload {
  anomaly_summary?: { total?: number }
}

function InsightRelatedSignals({ insight }: { insight: InsightOut }) {
  const [open, setOpen] = useState(false)
  const [phase, setPhase] = useState<'idle' | 'resolving' | 'ready' | 'empty' | 'error'>('idle')
  const [target, setTarget] = useState<{ datasetId: number; anomalyId: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const anomalySummary = (insight.payload as InsightPayload | undefined)?.anomaly_summary
  const hasAnomalies = (anomalySummary?.total ?? 0) > 0

  useEffect(() => {
    if (!open || phase !== 'idle') return
    const dsId = insight.dataset_id
    if (dsId == null) {
      setPhase('empty')
      return
    }
    let alive = true
    setPhase('resolving')
    api
      .anomalies(dsId, 3, 7)
      .then((res) => {
        if (!alive) return
        const list = res.anomalies ?? []
        if (list.length === 0) {
          setPhase('empty')
          return
        }
        const worst = list.reduce(
          (best, a, i) => (Math.abs(a.score) > Math.abs(best.score) ? { score: a.score, i } : best),
          { score: list[0].score, i: 0 }
        )
        setTarget({ datasetId: dsId, anomalyId: worst.i })
        setPhase('ready')
      })
      .catch((e) => {
        if (!alive) return
        setPhase('error')
        setError(e instanceof Error ? e.message : 'Failed to load related signals')
      })
    return () => {
      alive = false
    }
  }, [open, phase, insight.dataset_id])

  if (!hasAnomalies) return null

  return (
    <div className="mt-2">
      <button className="btn btn-ghost btn-sm" onClick={() => setOpen((o) => !o)}>
        <span
          style={{
            display: 'inline-flex',
            transform: open ? 'rotate(90deg)' : undefined,
            transition: 'transform var(--dur) var(--ease)',
          }}
        >
          <IconChevronRight size={13} />
        </span>
        See related signals
      </button>
      {open && (
        <div
          className="mt-2"
          style={{
            border: '1px solid var(--hairline)',
            borderRadius: 'var(--r-lg)',
            background: 'var(--surface-2)',
            padding: '8px 10px',
          }}
        >
          {phase === 'resolving' && (
            <div
              className="row"
              style={{ gap: 8, alignItems: 'center', color: 'var(--ink-mute)', fontSize: 12 }}
            >
              <span className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
              Checking related datasets…
            </div>
          )}
          {phase === 'ready' && target && (
            <RelatedSignalsPanel datasetId={target.datasetId} anomalyId={target.anomalyId} />
          )}
          {phase === 'empty' && (
            <div className="muted" style={{ fontSize: 12 }}>No related signals detected</div>
          )}
          {phase === 'error' && <div className="field-error">{error}</div>}
        </div>
      )}
    </div>
  )
}

export function Insights() {
  const toast = useToast()
  usePageTitle('Insights')
  const insights = useAsync<{ items: InsightOut[] }>(() => api.listInsights(1, 50), [])
  const datasets = useAsync(() => api.listDatasets(1, 100), [])
  const list = insights.data?.items ?? []
  const nameOf = new Map((datasets.data?.items ?? []).map((d) => [String(d.id), d.name]))

  async function generate() {
    const ds = datasets.data?.items ?? []
    if (ds.length === 0) {
      toast.push('Create a dataset first', 'err')
      return
    }
    try {
      await api.generateInsight(ds[0].id)
      toast.push('Insight generated')
      void insights.refetch()
    } catch (e) {
      toast.push(e instanceof Error ? e.message : 'Generation failed', 'err')
    }
  }

  async function remove(id: number) {
    try {
      await api.deleteInsight(id)
      void insights.refetch()
    } catch (e) {
      toast.push(e instanceof Error ? e.message : 'Delete failed', 'err')
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>AI Insights</h1>
          <p className="sub">Automated analysis of your datasets — trend, anomaly, and forecast summaries.</p>
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={() => void generate()}>
            <IconRefresh size={15} /> Generate insight
          </button>
        </div>
      </div>

      <div className="card">
        {insights.loading ? (
          <div className="empty"><span className="spinner" /></div>
        ) : list.length === 0 ? (
          <div className="empty">
            <span className="empty-state">
              <span className="ico"><IconSpark size={20} /></span>
              <h3>No insights yet</h3>
              <p>
                Generate one for your latest dataset — the engine analyzes trend,
                volatility, and anomalies.
              </p>
              <button className="btn btn-primary mt-4" onClick={() => void generate()}>
                <IconRefresh size={15} /> Generate insight
              </button>
            </span>
          </div>
        ) : (
          <div>
            {list.map((ins) => (
              <div key={ins.id} className="insight">
                <div className={`dot ${severityClass(ins.severity)}`} />
                <div className="body" style={{ flex: 1 }}>
                  <div className="title">{ins.title}</div>
                  <div className="text">{ins.body}</div>
                  {ins.payload && Object.keys(ins.payload).length > 0 && (
                    <div className="meta mono">{JSON.stringify(ins.payload)}</div>
                  )}
                  <div className="meta">
                    <span className="pill pill-ink">{ins.kind}</span>
                    <span className={`pill ${ins.severity === 'critical' ? 'pill-ruby' : ins.severity === 'warning' ? 'pill-amber' : 'pill-green'}`}>
                      {ins.severity}
                    </span>
                    <span>{nameOf.get(String(ins.dataset_id)) ?? '—'}</span>
                    <span className="num">{fmtDateTime(ins.created_at)}</span>
                  </div>
                  <InsightRelatedSignals insight={ins} />
                </div>
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ color: 'var(--ruby)', alignSelf: 'flex-start' }}
                  aria-label="Delete insight"
                  onClick={() => void remove(ins.id)}
                >
                  <IconTrash size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
