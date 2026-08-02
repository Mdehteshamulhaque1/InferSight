import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../app/providers/AuthContext'
import { api } from '../api'
import type {
  AnalyticsResponse,
  AnomalyResponse,
  DatasetRead,
  ForecastResponse,
  InsightOut,
  RecommendationOut,
  RootCauseOut,
} from '../types'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import { LineChart } from '../components/charts/LineChart'
import { Dropzone } from '../components/ui/Dropzone'
import { useToast } from '../components/ui/Toast'
import {
  IconBell,
  IconDownload,
  IconRefresh,
  IconShield,
  IconSpark,
  IconTrend,
  IconUpload,
} from '../components/ui/icons'
import { formatCompact, formatCurrency, formatPct, severityClass } from '../lib/format'

function KpiCard({
  label,
  value,
  change,
  spark,
  fmt,
}: {
  label: string
  value: number
  change?: number | null
  spark: { timestamp: string; value: number }[]
  fmt: (n: number) => string
}) {
  const up = change != null && change >= 0
  return (
    <div className="card kpi-card">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value num">{fmt(value)}</div>
      {change != null ? (
        <div className={`kpi-change num ${up ? 'up' : 'down'}`}>
          {up ? '▲' : '▼'} {Math.abs(change).toFixed(1)}% vs prior period
        </div>
      ) : (
        <div className="kpi-change" style={{ visibility: 'hidden' }}>·</div>
      )}
      {spark.length > 1 && (
        <div className="kpi-spark">
          <LineChart data={spark} height={30} formatY={() => ''} />
        </div>
      )}
    </div>
  )
}

function ForecastSummary({
  data,
  fmt,
}: {
  data: ForecastResponse
  fmt: (n: number) => string
}) {
  const pts = data.points ?? []
  const first = pts[0]
  const last = pts[pts.length - 1]
  const dir = last && first ? (last.value >= first.value ? '▲' : '▼') : null
  const chg =
    last && first && first.value !== 0
      ? ((last.value - first.value) / Math.abs(first.value)) * 100
      : null
  return (
    <div>
      <div className="kpi-grid">
        <div className="card kpi-card">
          <div className="kpi-label">Projected trend</div>
          <div className={`kpi-value num ${dir === '▲' ? 'up' : 'down'}`}>
            {dir ?? '—'} {chg != null ? `${Math.abs(chg).toFixed(1)}%` : ''}
          </div>
          <div className="kpi-change">over next {data.horizon} periods</div>
        </div>
        <div className="card kpi-card">
          <div className="kpi-label">Forecast endpoint</div>
          <div className="kpi-value num">{fmt(last?.value ?? 0)}</div>
          <div className="kpi-change">
            at{' '}
            {last
              ? new Date(last.timestamp).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                })
              : '—'}
          </div>
        </div>
        {(
          [
            ['MAPE', data.metrics.mape != null ? `${data.metrics.mape.toFixed(1)}%` : '—'],
            ['MAE', data.metrics.mae != null ? formatCompact(data.metrics.mae) : '—'],
            ['RMSE', data.metrics.rmse != null ? formatCompact(data.metrics.rmse) : '—'],
          ] as [string, string][]
        ).map(([k, v]) => (
          <div className="card kpi-card" key={k}>
            <div className="kpi-label">{k}</div>
            <div className="kpi-value num">{v}</div>
            <div className="kpi-change" style={{ visibility: 'hidden' }}>·</div>
          </div>
        ))}
      </div>
      <div className="row mt-6" style={{ gap: 8, flexWrap: 'wrap' }}>
        <span className="pill pill-soft">
          method <strong className="num">{data.method}</strong>
        </span>
        <span className="pill pill-soft">
          seasonality <strong className="num">{data.seasonality ? 'detected' : 'none'}</strong>
        </span>
        <span className="pill pill-soft">
          confidence band <strong className="num">80%</strong>
        </span>
      </div>
    </div>
  )
}

export function Dashboard() {
  const toast = useToast()
  const navigate = useNavigate()
  const { user } = useAuth()
  usePageTitle('Dashboard')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [tab, setTab] = useState<'series' | 'forecast'>('series')

  const datasets = useAsync(() => api.listDatasets(), [])
  const datasetsList = datasets.data?.items ?? []

  const firstName = user?.full_name?.trim().split(/\s+/)[0] || 'back'
  const greeting = `Welcome ${firstName}`

  function startUpload(file?: File) {
    navigate('/app/upload', file ? { state: { file } } : undefined)
  }

  const activeId = selectedId ?? datasetsList[0]?.id ?? null

  const analytics = useAsync<AnalyticsResponse>(
    () => (activeId != null ? api.analytics(activeId) : Promise.reject(new Error('no dataset'))),
    [activeId]
  )
  const anomalies = useAsync<AnomalyResponse>(
    () => (activeId != null ? api.anomalies(activeId) : Promise.reject(new Error('no dataset'))),
    [activeId]
  )
  const forecast = useAsync<ForecastResponse>(
    () =>
      activeId != null
        ? api.forecast(activeId, 30, 'auto')
        : Promise.reject(new Error('no dataset')),
    [activeId]
  )
  const insights = useAsync<{ items: InsightOut[] }>(() => api.listInsights(1, 20), [])
  const recommendations = useAsync<RecommendationOut[]>(
    () => (activeId != null ? api.recommendations(activeId) : Promise.reject(new Error('no dataset'))),
    [activeId]
  )
  const rootCause = useAsync<RootCauseOut>(
    () => (activeId != null ? api.rootCause(activeId) : Promise.reject(new Error('no dataset'))),
    [activeId]
  )

  const dataset: DatasetRead | undefined = datasetsList.find((d) => d.id === activeId)

  const kpis = analytics.data?.kpis ?? []
  const series = analytics.data?.series ?? []
  const trend = analytics.data?.trend
  const anomalyList = anomalies.data?.anomalies ?? []
  const forecastPts = forecast.data?.points ?? []

  const datasetName = useMemo(() => {
    const m = new Map<string, string>()
    for (const d of datasetsList) m.set(String(d.id), d.name)
    return m
  }, [datasetsList])

  async function exportAs(ext: 'csv' | 'xlsx' | 'pdf') {
    if (activeId == null) return
    try {
      const { blob, filename } = await api.exportReport(activeId, ext)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast.push(`Exported ${filename}`)
    } catch (e) {
      toast.push(e instanceof Error ? e.message : 'Export failed', 'err')
    }
  }

  async function generateInsight() {
    if (activeId == null) return
    try {
      await api.generateInsight(activeId)
      toast.push('Insight generated')
      void insights.refetch()
    } catch (e) {
      toast.push(e instanceof Error ? e.message : 'Generation failed', 'err')
    }
  }

  if (datasets.loading) {
    return <div className="empty"><span className="spinner" /></div>
  }

  if (datasetsList.length === 0) {
    return (
      <div>
        <div className="page-head">
          <div>
            <h1>{greeting}</h1>
            <p className="sub">Upload your first dataset — we’ll detect the columns and analyze it automatically.</p>
          </div>
        </div>

        <div className="card">
          <div className="wizard-hero">
            <h2>Upload your data</h2>
            <p>Drop a CSV and we’ll handle the rest. No forms, no setup.</p>
          </div>
          <Dropzone
            className="wizard-dropzone"
            onFile={(f) => startUpload(f)}
            title="Drop your CSV here"
            subtitle="or browse files · .csv, .xlsx, .xls, .json"
          />
          <div className="row mt-6" style={{ gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
            <span className="pill pill-green">Auto column detection</span>
            <span className="pill pill-green">Metric & granularity inferred</span>
            <span className="pill pill-green">Instant analysis</span>
          </div>
        </div>

        <div className="card mt-6">
          <div className="section-title">
            <span>Recent datasets</span>
          </div>
          <div className="empty">No datasets yet. Upload a CSV to generate your first business report.</div>
        </div>
      </div>
    )
  }

  const currency = dataset?.currency || null
  const fmt = (v: number) => formatCurrency(v, currency)

  return (
    <div>
        <div className="page-head">
          <div>
            <h1>{greeting}</h1>
            <p className="sub">Revenue intelligence across your connected datasets.</p>
          </div>
          <div className="actions">
            <button className="btn btn-primary" onClick={() => startUpload()} title="Upload a new data file">
              <IconUpload size={14} /> Upload your data
            </button>
          <select
            className="select"
            value={activeId ?? ''}
            onChange={(e) => setSelectedId(Number(e.target.value))}
            aria-label="Select dataset"
            style={{ minWidth: 180 }}
          >
            {datasetsList.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          <button className="btn btn-secondary" onClick={() => void exportAs('csv')} title="Export CSV">
            <IconDownload size={14} /> CSV
          </button>
          <button className="btn btn-secondary" onClick={() => void exportAs('xlsx')} title="Export XLSX">
            <IconDownload size={14} /> XLSX
          </button>
          <button className="btn btn-secondary" onClick={() => void exportAs('pdf')} title="Export PDF">
            <IconDownload size={14} /> PDF
          </button>
        </div>
      </div>

      <div className="kpi-grid">
        {kpis.map((k) => (
          <KpiCard
            key={k.key}
            label={k.label}
            value={k.value}
            change={k.change_pct}
            spark={series.slice(-28)}
            fmt={fmt}
          />
        ))}
      </div>

      <div className="card mt-6">
          <div className="section-title">
            <span>Time series</span>
            <div className="tabs" role="tablist">
              <button
                role="tab"
                aria-selected={tab === 'series'}
                className={`tab${tab === 'series' ? ' active' : ''}`}
                onClick={() => setTab('series')}
              >
                Series
              </button>
              <button
                role="tab"
                aria-selected={tab === 'forecast'}
                className={`tab${tab === 'forecast' ? ' active' : ''}`}
                onClick={() => setTab('forecast')}
              >
                Forecast
              </button>
            </div>
          </div>

          {analytics.loading || forecast.loading ? (
            <div className="empty"><span className="spinner" /></div>
          ) : tab === 'series' ? (
            <LineChart
              data={series}
              trend={trend?.fitted}
              anomalies={anomalyList}
              datasetId={activeId ?? undefined}
              height={320}
              formatY={fmt}
            />
          ) : (
            <LineChart data={series} forecast={forecastPts} height={320} formatY={fmt} />
          )}

          {tab === 'series' && trend && (
            <div className="row mt-8" style={{ gap: 12 }}>
              <span className="pill pill-ruby"><IconTrend size={11} /> {trend.direction}</span>
              <span className="meta-chip">
                r² <strong className="num">{trend.r_squared.toFixed(3)}</strong> · slope{' '}
                <strong className="num">{formatCompact(trend.slope)}/period</strong>
              </span>
            </div>
          )}
        </div>

      <div className="grid-2 mt-6">
        <div className="card">
          <div className="section-title">
            <span>Forecast · next {forecast.data?.horizon ?? 30} days</span>
            <span className="pill pill-soft num">{forecast.data?.method ?? '—'}</span>
          </div>
          {forecast.loading ? (
            <div className="empty"><span className="spinner" /></div>
          ) : !forecast.data ? (
            <div className="empty">{forecast.error ?? 'No forecast available.'}</div>
          ) : (
            <ForecastSummary data={forecast.data} fmt={fmt} />
          )}
        </div>

        <div className="card">
          <div className="section-title">
            <span><IconSpark size={15} /> AI summary</span>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => void generateInsight()}
              style={{ color: 'var(--primary)' }}
            >
              <IconRefresh size={13} /> Generate
            </button>
          </div>
          {insights.loading ? (
            <div className="empty"><span className="spinner" /></div>
          ) : (insights.data?.items ?? []).length === 0 ? (
            <div className="empty">Generate your first insight to see automated analysis.</div>
          ) : (
            <div style={{ maxHeight: 320, overflowY: 'auto' }}>
              {(insights.data?.items ?? []).map((ins) => (
                <div key={ins.id} className="insight">
                  <div className={`dot ${severityClass(ins.severity)}`} />
                  <div className="body">
                    <div className="title">{ins.title}</div>
                    <div className="text">{ins.body}</div>
                    <div className="meta">
                      <span className="pill pill-ink">{ins.kind}</span>
                      <span>{datasetName.get(String(ins.dataset_id)) ?? '—'}</span>
                      <span className="num">{new Date(ins.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid-2 mt-6">
        <div className="card">
          <div className="section-title">
            <span><IconShield size={15} /> Recommendations</span>
            {recommendations.data != null && (
              <span className="num muted">{recommendations.data.length}</span>
            )}
          </div>
          {recommendations.loading ? (
            <div className="empty"><span className="spinner" /></div>
          ) : (recommendations.data ?? []).length === 0 ? (
            <div className="empty">No recommendations available.</div>
          ) : (
            <div style={{ display: 'grid', gap: 12 }}>
              {recommendations.data?.map((r) => (
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

        <div className="card">
          <div className="section-title">
            <span><IconBell size={15} /> Root cause</span>
          </div>
          {rootCause.loading ? (
            <div className="empty"><span className="spinner" /></div>
          ) : rootCause.data ? (
            <div>
              <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                <div className="card kpi-card">
                  <div className="kpi-label">Actual</div>
                  <div className="kpi-value num">{fmt(rootCause.data.actual)}</div>
                </div>
                <div className="card kpi-card">
                  <div className="kpi-label">Expected</div>
                  <div className="kpi-value num">{fmt(rootCause.data.expected)}</div>
                </div>
                <div className="card kpi-card">
                  <div className="kpi-label">Delta</div>
                  <div className={`kpi-value num ${rootCause.data.delta >= 0 ? 'up' : 'down'}`}>
                    {formatPct(rootCause.data.delta_pct)}
                  </div>
                </div>
              </div>
              <div className="mt-6" style={{ display: 'grid', gap: 10 }}>
                {rootCause.data.hypotheses.slice(0, 3).map((h, i) => (
                  <div key={i} className="insight">
                    <div className="dot" style={{ background: 'var(--amber)' }} />
                    <div className="body">
                      <div className="title">{h.title}</div>
                      <div className="text">{h.evidence}</div>
                      <div className="meta"><span className="pill pill-ink">{h.confidence}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty">
              {rootCause.error ?? 'No anomalies detected, so there is nothing to root-cause yet.'}
            </div>
          )}
        </div>
      </div>

      <div className="grid-2 mt-6">
        <div className="card">
          <div className="section-title">
            <span>Anomalies</span>
            <span className="num muted">{anomalyList.length} flagged</span>
          </div>
          {anomalies.loading ? (
            <div className="empty"><span className="spinner" /></div>
          ) : anomalyList.length === 0 ? (
            <div className="empty">No anomalies detected in this window.</div>
          ) : (
            <div style={{ maxHeight: 320, overflowY: 'auto' }}>
              {anomalyList.slice(0, 8).map((a, i) => (
                <div key={`${a.timestamp}-${i}`} className="insight">
                  <div className={`dot ${severityClass(a.severity)}`} />
                  <div className="body">
                    <div className="row" style={{ gap: 8 }}>
                      <span className="pill pill-ruby">{a.direction}</span>
                      <span className="pill pill-ink num">{a.score.toFixed(1)}σ</span>
                    </div>
                    <div className="text mt-2">{a.reason}</div>
                    <div className="meta num">
                      {new Date(a.timestamp).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                      })}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="section-title">
            <span>Dataset health</span>
          </div>
          {analytics.data?.dataset && (
            <div className="table-wrap card-flat" style={{ boxShadow: 'none' }}>
              <table className="table">
                <tbody>
                  {[
                    ['Points', analytics.data.dataset.point_count],
                    ['Granularity', analytics.data.dataset.granularity],
                    ['Metric type', analytics.data.dataset.metric_type],
                    [
                      'Last point',
                      analytics.data.dataset.last_point_at
                        ? new Date(analytics.data.dataset.last_point_at).toLocaleDateString()
                        : '—',
                    ],
                    [
                      'Anomaly rate',
                      anomalies.data
                        ? `${((anomalies.data.anomalies.length / Math.max(1, anomalies.data.total_points)) * 100).toFixed(1)}%`
                        : '—',
                    ],
                    ['Forecast method', forecast.data?.method ?? '—'],
                  ].map(([k, v]) => (
                    <tr key={k}>
                      <td className="muted" style={{ fontSize: 12 }}>{k}</td>
                      <td className="strong num">{String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
