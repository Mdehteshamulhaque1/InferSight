import { useMemo, useState } from 'react'
import { api } from '../api'
import type {
  AnalyticsResponse,
  AnomalyResponse,
  DatasetRead,
  ForecastResponse,
  InsightOut,
} from '../types'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import { LineChart } from '../components/charts/LineChart'
import { useToast } from '../components/ui/Toast'
import { IconDataset, IconDownload, IconRefresh, IconSpark, IconTrend } from '../components/ui/icons'
import { formatCompact, formatCurrency, severityClass } from '../lib/format'

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

export function Dashboard() {
  const toast = useToast()
  usePageTitle('Dashboard')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [tab, setTab] = useState<'series' | 'forecast'>('series')

  const datasets = useAsync(() => api.listDatasets(), [])
  const datasetsList = datasets.data?.items ?? []

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
            <h1>Dashboard</h1>
            <p className="sub">Revenue intelligence across your connected datasets.</p>
          </div>
        </div>
        <div className="card">
          <div className="empty">
            <span className="empty-state">
              <span className="ico"><IconDataset size={20} /></span>
              <h3>No datasets yet</h3>
              <p>Create one from the Datasets page to start seeing KPIs, forecasts, and insights.</p>
            </span>
          </div>
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
          <h1>Dashboard</h1>
          <p className="sub">Revenue intelligence across your connected datasets.</p>
        </div>
        <div className="actions">
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

      <div className="grid-2-1 mt-6">
        <div className="card">
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

          {tab === 'forecast' && forecast.data && (
            <div className="row mt-8" style={{ gap: 20, flexWrap: 'wrap' }}>
              <span className="meta-chip">
                method <strong className="num">{forecast.data.method}</strong>
              </span>
              <span className="meta-chip">
                horizon <strong className="num">{forecast.data.horizon}d</strong>
              </span>
              {forecast.data.metrics.mape != null && (
                <span className="meta-chip">
                  MAPE <strong className="num">{forecast.data.metrics.mape.toFixed(1)}%</strong>
                </span>
              )}
              {forecast.data.metrics.mae != null && (
                <span className="meta-chip">
                  MAE <strong className="num">{formatCompact(forecast.data.metrics.mae)}</strong>
                </span>
              )}
              {forecast.data.metrics.rmse != null && (
                <span className="meta-chip">
                  RMSE <strong className="num">{formatCompact(forecast.data.metrics.rmse)}</strong>
                </span>
              )}
            </div>
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
            <div style={{ maxHeight: 340, overflowY: 'auto' }}>
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
      </div>

      <div className="grid-2 mt-6">
        <div className="card">
          <div className="section-title">
            <span><IconSpark size={15} /> AI insights</span>
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
