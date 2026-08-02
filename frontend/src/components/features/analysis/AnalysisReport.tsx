import { useState } from 'react'
import type { CSSProperties } from 'react'
import { api } from '../../../api'
import { useAsync } from '../../../hooks/useAsync'
import { LineChart } from '../../charts/LineChart'
import {
  IconArrowLeft,
  IconArrowRight,
  IconCheck,
} from '../../ui/icons'
import {
  formatCurrency,
  formatPct,
  severityClass,
} from '../../../lib/format'
import type { AnalysisSummary } from '../../../types'

const STEPS = [
  { key: 'health', label: 'Business health' },
  { key: 'trend', label: 'Revenue trend' },
  { key: 'anomalies', label: 'Anomalies' },
  { key: 'forecast', label: 'Forecast' },
  { key: 'recommendations', label: 'Recommendations' },
]

export function AnalysisReport({
  summary,
  onClose,
}: {
  summary: AnalysisSummary
  onClose: () => void
}) {
  const [step, setStep] = useState(0)

  const analytics = useAsync(() => api.analytics(summary.dataset_id), [summary.dataset_id])
  const anomalies = useAsync(
    () => api.anomalies(summary.dataset_id),
    [summary.dataset_id]
  )
  const recommendations = useAsync(
    () => api.recommendations(summary.dataset_id),
    [summary.dataset_id]
  )

  const currency = summary.currency
  const fmt = (v: number) => formatCurrency(v, currency)
  const series = analytics.data?.series ?? []
  const anomalyList = anomalies.data?.anomalies ?? []
  const recs = recommendations.data ?? []

  const health = summary.health
  const mainKpi = summary.kpis[0]

  return (
    <div className="report">
      <div className="report-head">
        <div>
          <span className="report-eyebrow">Guided analysis</span>
          <h2>{summary.name}</h2>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Back to chat
        </button>
      </div>

      <div className="report-steps" role="tablist" aria-label="Analysis steps">
        {STEPS.map((s, i) => (
          <button
            key={s.key}
            role="tab"
            aria-selected={i === step}
            className={`report-step${i === step ? ' active' : ''}${i < step ? ' done' : ''}`}
            onClick={() => setStep(i)}
          >
            <span className="idx">{i < step ? <IconCheck size={12} /> : i + 1}</span>
            <span className="label">{s.label}</span>
          </button>
        ))}
      </div>

      <div className="report-body">
        {step === 0 && (
          <div className="report-panel">
            <div className="row" style={{ gap: 20, alignItems: 'center' }}>
              <div
                className={`health-ring ${health.score >= 75 ? 'good' : health.score >= 50 ? 'fair' : 'poor'}`}
                style={{ '--score': health.score } as CSSProperties}
              >
                {health.score}
              </div>
              <div>
                <div className="row" style={{ gap: 8 }}>
                  <span className="pill pill-soft">Grade {health.grade}</span>
                  <span className="pill pill-green">{health.verdict}</span>
                </div>
                <p className="muted mt-4" style={{ maxWidth: 480 }}>
                  A composite 0–100 score across freshness, completeness, stability,
                  anomaly pressure, and momentum.
                </p>
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="report-panel">
            {analytics.loading ? (
              <div className="empty"><span className="spinner" /></div>
            ) : (
              <>
                <LineChart data={series} trend={analytics.data?.trend?.fitted} height={220} formatY={fmt} />
                <div className="row mt-6" style={{ gap: 10, flexWrap: 'wrap' }}>
                  <span className={`pill ${summary.trend.direction === 'up' ? 'pill-green' : summary.trend.direction === 'down' ? 'pill-ruby' : 'pill-soft'}`}>
                    {summary.trend.direction === 'up' ? '▲' : summary.trend.direction === 'down' ? '▼' : '—'} {summary.trend.direction}
                  </span>
                  {mainKpi && mainKpi.change_pct != null && (
                    <span className="meta-chip">
                      latest period <strong className="num">{formatPct(mainKpi.change_pct)}</strong>
                    </span>
                  )}
                  <span className="meta-chip">
                    slope <strong className="num">{summary.trend.slope_per_period_pct.toFixed(1)}%/period</strong>
                  </span>
                  <span className="meta-chip">
                    fit r² <strong className="num">{summary.trend.r_squared.toFixed(3)}</strong>
                  </span>
                </div>
              </>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="report-panel">
            {anomalies.loading ? (
              <div className="empty"><span className="spinner" /></div>
            ) : anomalyList.length === 0 ? (
              <div className="empty">No anomalies detected — your series looks clean.</div>
            ) : (
              <div style={{ display: 'grid', gap: 10 }}>
                {anomalyList.slice(0, 4).map((a, i) => (
                  <div key={`${a.timestamp}-${i}`} className="insight">
                    <div className={`dot ${severityClass(a.severity)}`} />
                    <div className="body">
                      <div className="row" style={{ gap: 8 }}>
                        <span className="pill pill-ruby">{a.direction}</span>
                        <span className="pill pill-ink num">{a.score.toFixed(1)}σ</span>
                      </div>
                      <div className="text mt-2">{a.reason}</div>
                      <div className="meta num">
                        {new Date(a.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="report-panel">
            {summary.forecast ? (
              <>
                <LineChart
                  data={series}
                  forecast={summary.forecast.points}
                  height={220}
                  formatY={fmt}
                />
                <div className="row mt-6" style={{ gap: 10, flexWrap: 'wrap' }}>
                  <span className="pill pill-soft">
                    method <strong className="num">{summary.forecast.method}</strong>
                  </span>
                  <span className="meta-chip">
                    horizon <strong className="num">{summary.forecast.horizon}d</strong>
                  </span>
                  {summary.forecast.mape != null && (
                    <span className="meta-chip">
                      MAPE <strong className="num">{summary.forecast.mape.toFixed(1)}%</strong>
                    </span>
                  )}
                  {summary.forecast.points.length > 1 && (
                    <span className="meta-chip">
                      endpoint{' '}
                      <strong className="num">
                        {fmt(summary.forecast.points[summary.forecast.points.length - 1].value)}
                      </strong>
                    </span>
                  )}
                </div>
              </>
            ) : (
              <div className="empty">Forecast unavailable for this series.</div>
            )}
          </div>
        )}

        {step === 4 && (
          <div className="report-panel">
            {recommendations.loading ? (
              <div className="empty"><span className="spinner" /></div>
            ) : recs.length === 0 ? (
              <div className="empty">No recommendations available.</div>
            ) : (
              <div style={{ display: 'grid', gap: 12 }}>
                {recs.slice(0, 5).map((r) => (
                  <div key={r.id} className="row" style={{ gap: 14, alignItems: 'flex-start' }}>
                    <span className={`pill ${r.severity === 'critical' ? 'pill-primary' : r.severity === 'warning' ? 'pill-ink' : 'pill-soft'}`}>
                      {r.severity}
                    </span>
                    <div>
                      <div className="strong">{r.action}</div>
                      <div className="muted" style={{ fontSize: 13 }}>{r.rationale}</div>
                      <div className="meta num" style={{ fontSize: 12 }}>{r.category} · {r.impact}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="report-nav">
        <button className="btn btn-secondary" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
          <IconArrowLeft size={14} /> Back
        </button>
        <span className="muted num">
          Step {step + 1} of {STEPS.length}
        </span>
        {step < STEPS.length - 1 ? (
          <button className="btn btn-primary" onClick={() => setStep((s) => s + 1)}>
            Next: {STEPS[step + 1].label} <IconArrowRight size={14} />
          </button>
        ) : (
          <button className="btn btn-primary" onClick={onClose}>
            Ask about this report <IconArrowRight size={14} />
          </button>
        )}
      </div>
    </div>
  )
}

export function AnalysisChecklist({ summary }: { summary: AnalysisSummary }) {
  const kpi = summary.kpis[0]
  const change = kpi?.change_pct
  const items: { label: string; value: string; ok: boolean }[] = [
    {
      label: kpi ? `${kpi.label} ${summary.trend.direction}` : 'Trend analyzed',
      value: change != null ? formatPct(change) : summary.trend.slope_per_period_pct.toFixed(1) + '%/period',
      ok: true,
    },
    {
      label: 'Anomalies',
      value: `${summary.anomaly_count} detected`,
      ok: true,
    },
    {
      label: 'Forecast',
      value: summary.forecast ? `generated · ${summary.forecast.horizon}d` : 'generated',
      ok: !!summary.forecast,
    },
    {
      label: 'Health score',
      value: `${summary.health.score} / 100`,
      ok: true,
    },
  ]
  return (
    <div className="checklist">
      <div className="checklist-title">
        <span className="checklist-check"><IconCheck size={14} /></span>
        Analysis complete
      </div>
      <div className="checklist-grid">
        {items.map((it) => (
          <div key={it.label} className={`checklist-item${it.ok ? ' ok' : ''}`}>
            <span className="check">{it.ok ? <IconCheck size={12} /> : '…'}</span>
            <div>
              <div className="label">{it.label}</div>
              <div className="value num">{it.value}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function demoCSV(): File {
  const rows: string[] = ['timestamp,revenue']
  const start = new Date(Date.UTC(2026, 0, 1))
  let seed = 42
  const rand = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff
    return seed / 0x7fffffff
  }
  for (let i = 0; i < 90; i++) {
    let v = 4200 + i * 48 + rand() * 140 - 70
    if (i % 7 === 3) v += 320
    if (i === 48) v += 4300
    const ts = new Date(start.getTime() + i * 86_400_000).toISOString()
    rows.push(`${ts},${Math.round(v)}`)
  }
  return new File([rows.join('\n')], 'demo-sales.csv', { type: 'text/csv' })
}
