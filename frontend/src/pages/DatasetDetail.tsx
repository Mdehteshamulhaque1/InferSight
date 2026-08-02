import { useMemo, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import type {
  HealthScoreOut,
  Kpi,
  ProfileOut,
  RecommendationOut,
  RootCauseOut,
} from '../types'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import { useToast } from '../components/ui/Toast'
import { AlertRulesPanel } from '../components/features/alert-rules/AlertRulesPanel'
import {
  IconArrowLeft,
  IconArrowRight,
  IconChat,
  IconClock,
  IconFile,
  IconHealth,
  IconRefresh,
  IconSearch,
  IconShield,
  IconUpload,
} from '../components/ui/icons'
import { fmtDate, formatCurrency, formatPct } from '../lib/format'

type Tab = 'overview' | 'profile' | 'root-cause' | 'chat' | 'versions' | 'alert-rules'

interface ChatMessage {
  role: 'user' | 'ai'
  text: string
  intent?: string
  followups?: string[]
}

function HealthRing({ health }: { health: HealthScoreOut }) {
  const r = 44
  const c = 2 * Math.PI * r
  const pct = health.score / 100
  const color =
    health.score >= 75 ? 'var(--green)' : health.score >= 55 ? 'var(--amber)' : 'var(--ruby)'
  return (
    <div className="row" style={{ gap: 20, alignItems: 'center' }}>
      <svg width={116} height={116} viewBox="0 0 116 116" aria-hidden="true">
        <circle cx={58} cy={58} r={r} fill="none" stroke="var(--hairline)" strokeWidth={10} />
        <circle
          cx={58}
          cy={58}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={10}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          transform="rotate(-90 58 58)"
        />
        <text x={58} y={52} textAnchor="middle" className="ring-score">
          {health.score}
        </text>
        <text x={58} y={72} textAnchor="middle" className="ring-grade">
          grade {health.grade}
        </text>
      </svg>
      <div>
        <div className="strong" style={{ fontSize: 18 }}>{health.verdict}</div>
        <div className="muted" style={{ maxWidth: 300 }}>
          {health.components
            .slice()
            .sort((a, b) => a.score - b.score)
            .map((c) => c.label)
            .join(' · ')}
        </div>
      </div>
    </div>
  )
}

function HealthBars({ health }: { health: HealthScoreOut }) {
  return (
    <div className="mt-6" style={{ display: 'grid', gap: 10 }}>
      {health.components.map((c) => (
        <div key={c.key}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
            <span className="muted" style={{ fontSize: 12 }}>{c.label}</span>
            <span className="num" style={{ fontSize: 12 }}>{c.score.toFixed(0)}</span>
          </div>
          <div className="bar">
            <div
              className={`bar-fill ${c.score >= 75 ? 'bar-good' : c.score >= 50 ? 'bar-mid' : 'bar-bad'}`}
              style={{ width: `${Math.max(3, c.score)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function Dropzone({
  file,
  onFile,
  replace,
  onReplace,
}: {
  file: File | null
  onFile: (f: File | null) => void
  replace: boolean
  onReplace: (v: boolean) => void
}) {
  const [drag, setDrag] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <div
      className={`dropzone${drag ? ' drag' : ''}`}
      role="button"
      tabIndex={0}
      aria-label="Upload a data file"
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
      }}
      onDragOver={(e) => {
        e.preventDefault()
        setDrag(true)
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDrag(false)
        const f = e.dataTransfer.files?.[0]
        if (f) onFile(f)
      }}
    >
      <span className="ico"><IconUpload size={18} /></span>
      {file ? (
        <>
          <span className="fname">{file.name}</span>
          <span className="fsub">
            {(file.size / 1024).toFixed(1)} KB — click to change or drop another file
          </span>
        </>
      ) : (
        <>
          <span className="fname">Drop a file here, or click to browse</span>
          <span className="fsub">.csv, .xlsx, .xls, or .json — column detection is automatic</span>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx,.xls,.json"
        onChange={(e: ChangeEvent<HTMLInputElement>) => onFile(e.target.files?.[0] ?? null)}
      />
      {file && (
        <span
          className="row"
          style={{ gap: 6, marginTop: 6 }}
          onClick={(e) => e.stopPropagation()}
        >
          <label className="check" style={{ marginBottom: 0 }}>
            <input type="checkbox" checked={replace} onChange={(e) => onReplace(e.target.checked)} />
            <span className="box" />
            <span style={{ fontSize: 13, color: 'var(--ink-mute)' }}>replace existing points</span>
          </label>
        </span>
      )}
    </div>
  )
}

export function DatasetDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const datasetId = Number(id)
  const [tab, setTab] = useState<Tab>('overview')
  const [file, setFile] = useState<File | null>(null)
  const [replace, setReplace] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [chatInput, setChatInput] = useState('')
  const [chatBusy, setChatBusy] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])

  const dataset = useAsync(() => api.getDataset(datasetId), [datasetId])
  const health = useAsync<HealthScoreOut>(
    () => (datasetId ? api.health(datasetId) : Promise.reject(new Error('no id'))),
    [datasetId]
  )
  const kpis = useAsync<Kpi[]>(
    () => (datasetId ? api.discoverKpis(datasetId) : Promise.reject(new Error('no id'))),
    [datasetId]
  )
  const profile = useAsync<ProfileOut>(
    () => (datasetId ? api.profile(datasetId) : Promise.reject(new Error('no id'))),
    [datasetId]
  )
  const recommendations = useAsync<RecommendationOut[]>(
    () => (datasetId ? api.recommendations(datasetId) : Promise.reject(new Error('no id'))),
    [datasetId]
  )
  const rootCause = useAsync<RootCauseOut>(
    () => (datasetId ? api.rootCause(datasetId) : Promise.reject(new Error('no id'))),
    [datasetId]
  )
  const versions = useAsync(() => api.listVersions(datasetId), [datasetId])

  const ds = dataset.data
  usePageTitle(ds ? ds.name : 'Dataset')

  const currency = ds?.currency || null
  const fmt = useMemo(() => (n: number) => formatCurrency(n, currency), [currency])

  async function onUpload(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setUploading(true)
    setUploadError(null)
    setUploadResult(null)
    try {
      const res = await api.ingestFile(datasetId, file, replace)
      setUploadResult(
        `Imported ${res.inserted} point${res.inserted === 1 ? '' : 's'} from ${res.filename} ` +
          `(detected ${res.detected_granularity} granularity, column "${res.value_column}"). ` +
          `${res.skipped_duplicates} duplicates skipped${res.replaced ? ' — replaced all prior points' : ''}.`
      )
      toast.push('File imported')
      void dataset.refetch()
      void versions.refetch()
      setFile(null)
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function ask(message: string) {
    const q = message.trim()
    if (!q || chatBusy) return
    setMessages((m) => [...m, { role: 'user', text: q }])
    setChatInput('')
    setChatBusy(true)
    try {
      const res = await api.chat(q, datasetId)
      setMessages((m) => [
        ...m,
        { role: 'ai', text: res.reply, intent: res.intent, followups: res.followups },
      ])
    } catch (err) {
      toast.push(err instanceof Error ? err.message : 'Chat failed', 'err')
      setMessages((m) => [...m, { role: 'ai', text: 'Sorry — I couldn’t reach the engine right now.' }])
    } finally {
      setChatBusy(false)
    }
  }

  function onSendChat(e: FormEvent) {
    e.preventDefault()
    void ask(chatInput)
  }

  async function onSyncAlerts() {
    try {
      const res = await api.syncAlerts(datasetId)
      toast.push(`${res.alerts_created} alert${res.alerts_created === 1 ? '' : 's'} created`)
    } catch (e) {
      toast.push(e instanceof Error ? e.message : 'Sync failed', 'err')
    }
  }

  async function onRollback(versionNo: number) {
    if (!window.confirm(`Roll "${ds?.name}" back to version ${versionNo}? Current points will be replaced.`)) return
    try {
      const res = await api.rollbackVersion(datasetId, versionNo)
      toast.push(res.detail)
      void versions.refetch()
      void dataset.refetch()
    } catch (e) {
      toast.push(e instanceof Error ? e.message : 'Rollback failed', 'err')
    }
  }

  if (dataset.loading) return <div className="empty"><span className="spinner" /></div>
  if (!ds) {
    return (
      <div className="card mt-6">
        <div className="empty">
          <span className="empty-state">
            <span className="ico"><IconFile size={20} /></span>
            <h3>Dataset not found</h3>
            <Link className="btn btn-secondary mt-4" to="/app/datasets">Back to datasets</Link>
          </span>
        </div>
      </div>
    )
  }

  const stats = profile.data?.stats
  const quality = profile.data?.quality

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'profile', label: 'Profile' },
    { key: 'root-cause', label: 'Root cause' },
    { key: 'chat', label: 'Ask' },
    { key: 'versions', label: 'Versions' },
    { key: 'alert-rules', label: 'Alert rules' },
  ]

  return (
    <div>
      <div className="page-head">
        <div>
          <Link to="/app/datasets" className="back-link">
            <IconArrowLeft size={13} /> Datasets
          </Link>
          <h1>{ds.name}</h1>
          <p className="sub">
            <span className="mono">/{ds.slug}</span>
            <span className="pill pill-soft">{ds.metric_type}</span>
            <span className="pill pill-soft">{ds.granularity}</span>
            <span className="num">{ds.point_count.toLocaleString()} points</span>
          </p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary" onClick={() => void onSyncAlerts()}>
            <IconRefresh size={14} /> Sync alerts
          </button>
          <button className="btn btn-primary" onClick={() => void navigate('/app/dashboard')}>
            Open dashboard <IconArrowRight size={13} />
          </button>
        </div>
      </div>

      <div className="tabs mb-6">
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            className={`tab${tab === t.key ? ' active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <>
          <div className="grid-2">
            <div className="card">
              <div className="section-title">
                <span><IconHealth size={15} /> Business health</span>
              </div>
              {health.loading ? (
                <div className="empty"><span className="spinner" /></div>
              ) : health.data ? (
                <>
                  <HealthRing health={health.data} />
                  <HealthBars health={health.data} />
                </>
              ) : (
                <div className="empty">{health.error ?? 'No health score available.'}</div>
              )}
            </div>

            <div className="card">
              <div className="section-title">
                <span>Discovered KPIs</span>
              </div>
              {kpis.loading ? (
                <div className="empty"><span className="spinner" /></div>
              ) : (kpis.data ?? []).length === 0 ? (
                <div className="empty">No KPIs discovered yet — import data first.</div>
              ) : (
                <div className="kpi-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
                  {kpis.data?.slice(0, 6).map((k) => {
                    const up = k.change_pct != null && k.change_pct >= 0
                    return (
                      <div key={k.key} className="card kpi-card">
                        <div className="kpi-label">{k.label}</div>
                        <div className="kpi-value num">{fmt(k.value)}</div>
                        {k.change_pct != null && (
                          <div className={`kpi-change num ${up ? 'up' : 'down'}`}>
                            {up ? '▲' : '▼'} {Math.abs(k.change_pct).toFixed(1)}%
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="card mt-6">
            <div className="section-title">
              <span><IconShield size={15} /> Recommendations</span>
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

          <div className="card mt-6">
            <div className="section-title">
              <span><IconUpload size={15} /> Import data</span>
            </div>
            <div className="muted mb-6" style={{ maxWidth: 640 }}>
              Upload a <code className="mono">.csv</code>, <code className="mono">.xlsx</code>, or{' '}
              <code className="mono">.json</code> file. Column detection is automatic (timestamp +
              value columns are sniffed); ingestion is idempotent.
            </div>
            <form onSubmit={onUpload}>
              <Dropzone
                file={file}
                onFile={setFile}
                replace={replace}
                onReplace={setReplace}
              />
              {uploadResult && <div className="pill pill-green mt-4">{uploadResult}</div>}
              {uploadError && <div className="field-error mt-4">{uploadError}</div>}
              {file && (
                <div className="row mt-6" style={{ gap: 10 }}>
                  <button className="btn btn-primary" type="submit" disabled={uploading}>
                    {uploading ? <span className="spinner" /> : `Import ${file.name}`}
                  </button>
                  <button className="btn btn-secondary" type="button" onClick={() => setFile(null)}>
                    Cancel
                  </button>
                </div>
              )}
            </form>
          </div>
        </>
      )}

      {tab === 'profile' && (
        <>
          {profile.loading ? (
            <div className="empty"><span className="spinner" /></div>
          ) : !profile.data ? (
            <div className="empty">{profile.error ?? 'No profile available.'}</div>
          ) : (
            <>
              <div className="kpi-grid">
                {[
                  ['Points', profile.data.count],
                  ['Mean', stats?.mean ?? 0],
                  ['Median', stats?.median ?? 0],
                  ['Std dev', stats?.std ?? 0],
                  ['Volatility (CV)', stats?.cv ?? 0],
                  ['Span (days)', profile.data.span_days],
                ].map(([label, value]) => (
                  <div key={String(label)} className="card kpi-card">
                    <div className="kpi-label">{label}</div>
                    <div className="kpi-value num">{typeof value === 'number' ? fmt(value) : value}</div>
                  </div>
                ))}
              </div>

              <div className="grid-2 mt-6">
                <div className="card">
                  <div className="section-title"><span>Trend & seasonality</span></div>
                  <table className="table">
                    <tbody>
                      <tr><td className="muted">Direction</td><td className="strong num">{profile.data.trend.direction}</td></tr>
                      <tr><td className="muted">Slope per period</td><td className="strong num">{profile.data.trend.slope_per_period_pct.toFixed(3)}%</td></tr>
                      <tr><td className="muted">Fit R²</td><td className="strong num">{profile.data.trend.r_squared.toFixed(3)}</td></tr>
                      <tr><td className="muted">Seasonality</td><td className="strong num">{profile.data.seasonality.strength} (lag {profile.data.seasonality.lag}, ρ={profile.data.seasonality.correlation.toFixed(2)})</td></tr>
                    </tbody>
                  </table>
                </div>

                <div className="card">
                  <div className="section-title"><span>Data quality</span></div>
                  <table className="table">
                    <tbody>
                      <tr><td className="muted">Completeness</td><td className="strong num">{quality?.completeness_pct.toFixed(1)}%</td></tr>
                      <tr><td className="muted">Missing periods</td><td className="strong num">{quality?.missing_periods}</td></tr>
                      <tr><td className="muted">Negative values</td><td className="strong num">{quality?.negative_count}</td></tr>
                      <tr><td className="muted">Zeros</td><td className="strong num">{quality?.zero_count}</td></tr>
                      <tr><td className="muted">Freshness</td><td className="strong num">{quality ? `${quality.freshness_hours.toFixed(0)}h ago` : '—'}</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="grid-2 mt-6">
                <div className="card">
                  <div className="section-title"><span>Top points</span></div>
                  {profile.data.top_points.map((p) => (
                    <div key={String(p.timestamp)} className="insight">
                      <div className="dot positive" />
                      <div className="body">
                        <div className="row" style={{ justifyContent: 'space-between' }}>
                          <span className="muted">{fmtDate(p.timestamp)}</span>
                          <span className="num strong">{fmt(p.value)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="card">
                  <div className="section-title"><span>Biggest swings</span></div>
                  {profile.data.biggest_movers.map((m, i) => (
                    <div key={i} className="insight">
                      <div className={`dot ${m.change_pct >= 0 ? 'positive' : 'critical'}`} />
                      <div className="body">
                        <div className="row" style={{ justifyContent: 'space-between' }}>
                          <span className="muted">{fmtDate(m.to)}</span>
                          <span className={`num strong ${m.change_pct >= 0 ? 'up' : 'down'}`}>
                            {formatPct(m.change_pct)}
                          </span>
                        </div>
                        <div className="meta num" style={{ fontSize: 12 }}>
                          {fmt(m.from_value)} → {fmt(m.to_value)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </>
      )}

      {tab === 'root-cause' && (
        <div className="card">
          <div className="section-title">
            <span><IconSearch size={15} /> Root-cause analysis</span>
          </div>
          {rootCause.loading ? (
            <div className="empty"><span className="spinner" /></div>
          ) : rootCause.data ? (
            <>
              <div className="kpi-grid">
                <div className="card kpi-card">
                  <div className="kpi-label">Observed</div>
                  <div className="kpi-value num">{fmt(rootCause.data.actual)}</div>
                </div>
                <div className="card kpi-card">
                  <div className="kpi-label">Expected</div>
                  <div className="kpi-value num">{fmt(rootCause.data.expected)}</div>
                </div>
                <div className="card kpi-card">
                  <div className="kpi-label">Deviation</div>
                  <div className={`kpi-value num ${rootCause.data.delta >= 0 ? 'up' : 'down'}`}>
                    {formatPct(rootCause.data.delta_pct)}
                  </div>
                </div>
                <div className="card kpi-card">
                  <div className="kpi-label">Date</div>
                  <div className="kpi-value num" style={{ fontSize: 15 }}>
                    {fmtDate(rootCause.data.timestamp)}
                  </div>
                </div>
              </div>

              <div className="grid-2 mt-6">
                <div>
                  <h3 style={{ fontSize: 14, marginBottom: 12 }}>Hypotheses</h3>
                  <div style={{ display: 'grid', gap: 12 }}>
                    {rootCause.data.hypotheses.map((h, i) => (
                      <div key={i} className="card card-flat">
                        <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                          <span className="strong" style={{ fontSize: 14 }}>{h.title}</span>
                          <span className={`pill ${h.confidence === 'high' ? 'pill-ruby' : h.confidence === 'medium' ? 'pill-ink' : 'pill-soft'}`}>
                            {h.confidence}
                          </span>
                        </div>
                        <div className="muted mt-2" style={{ fontSize: 13 }}>{h.evidence}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 style={{ fontSize: 14, marginBottom: 12 }}>Calendar effects</h3>
                  <table className="table">
                    <tbody>
                      {rootCause.data.time_effects.map((t) => (
                        <tr key={t.factor}>
                          <td className="muted">{t.factor === 'day_of_week' ? 'Day of week' : 'Month'}</td>
                          <td className="strong num">{t.value}</td>
                          <td className={`num ${t.relative_change_pct >= 0 ? 'up' : 'down'}`}>
                            {formatPct(t.relative_change_pct)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {rootCause.data.contributing_segments.length > 0 && (
                    <>
                      <h3 style={{ fontSize: 14, margin: '16px 0 12px' }}>Contributing segments</h3>
                      <table className="table">
                        <thead>
                          <tr><th>Dimension</th><th>Segment</th><th className="num">Δ</th><th className="num">Weight</th></tr>
                        </thead>
                        <tbody>
                          {rootCause.data.contributing_segments.map((s, i) => (
                            <tr key={i}>
                              <td className="muted">{s.dimension}</td>
                              <td className="strong">{s.segment}</td>
                              <td className={`num ${s.change_pct >= 0 ? 'up' : 'down'}`}>{formatPct(s.change_pct)}</td>
                              <td className="num">{(s.weight * 100).toFixed(0)}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="empty">
              {rootCause.error ??
                'No anomalies detected, so there is nothing to root-cause yet.'}
            </div>
          )}
        </div>
      )}

      {tab === 'chat' && (
        <div className="grid-2">
          <div className="card">
            <div className="section-title">
              <span><IconChat size={15} /> Ask about this dataset</span>
            </div>
            <div className="muted mb-6" style={{ maxWidth: 560 }}>
              Natural-language questions like "what is the trend?", "explain the spike on Feb 10",
              "how healthy is this?", or "what should I do next?".
            </div>

            <div className="chat-bubbles">
              {messages.length === 0 && (
                <div className="empty" style={{ padding: '24px 0' }}>
                  Ask something to get a written analysis.
                </div>
              )}
              {messages.map((m, i) => (
                <div key={i} className={`bubble ${m.role}`}>
                  {m.text}
                  {m.intent && (
                    <div style={{ fontSize: 11, opacity: 0.6, marginTop: 6 }}>intent: {m.intent}</div>
                  )}
                </div>
              ))}
              {chatBusy && (
                <div className="bubble ai">
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                </div>
              )}
            </div>

            <form onSubmit={onSendChat} className="chat-input-row mt-6">
              <input
                className="input"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask anything about the data…"
                aria-label="Ask a question"
                style={{ flex: 1 }}
              />
              <button className="btn btn-primary" type="submit" disabled={chatBusy || !chatInput.trim()}>
                {chatBusy ? <span className="spinner" /> : 'Ask'}
              </button>
            </form>

            {messages.filter((m) => m.role === 'ai' && m.followups?.length).length > 0 && (
              <div className="row mt-6" style={{ gap: 8, flexWrap: 'wrap' }}>
                {messages
                  .filter((m) => m.role === 'ai' && m.followups?.length)
                  .slice(-1)[0]?.followups?.map((f) => (
                    <button key={f} className="pill pill-soft followup" onClick={() => void ask(f)}>
                      {f}
                    </button>
                  ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="section-title">
              <span><IconClock size={15} /> Version history</span>
            </div>
            {versions.loading ? (
              <div className="empty"><span className="spinner" /></div>
            ) : (versions.data?.items ?? []).length === 0 ? (
              <div className="empty">No versions recorded yet.</div>
            ) : (
              <div style={{ display: 'grid', gap: 10, maxHeight: 480, overflowY: 'auto' }}>
                {versions.data?.items.map((v) => (
                  <div key={v.id} className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                    <div>
                      <div className="row" style={{ gap: 8 }}>
                        <span className="pill pill-soft">v{v.version_no}</span>
                        <span className="pill pill-ink">{v.source}</span>
                        {v.status !== 'success' && <span className="pill pill-ruby">{v.status}</span>}
                      </div>
                      <div className="meta num" style={{ fontSize: 12, marginTop: 4 }}>
                        {new Date(v.created_at).toLocaleString()} · +{v.points_added} · −{v.points_removed} · {v.total_after} points
                        {v.filename ? ` · ${v.filename}` : ''}
                      </div>
                    </div>
                    <button className="btn btn-ghost btn-sm" onClick={() => void onRollback(v.version_no)}>
                      Roll back
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'versions' && (
        <div className="card">
          <div className="section-title">
            <span><IconClock size={15} /> Version history</span>
          </div>
          {versions.loading ? (
            <div className="empty"><span className="spinner" /></div>
          ) : (versions.data?.items ?? []).length === 0 ? (
            <div className="empty">No versions recorded yet. Every bulk ingest writes a snapshot you can roll back to.</div>
          ) : (
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Source</th>
                    <th>File</th>
                    <th className="num">Added</th>
                    <th className="num">Removed</th>
                    <th className="num">Total after</th>
                    <th>When</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {versions.data?.items.map((v) => (
                    <tr key={v.id}>
                      <td><span className="pill pill-soft">v{v.version_no}</span></td>
                      <td className="strong">
                        {v.source}
                        {v.status !== 'success' && <span className="pill pill-ruby" style={{ marginLeft: 6 }}>{v.status}</span>}
                      </td>
                      <td className="meta">{v.filename ?? '—'}</td>
                      <td className="num">+{v.points_added}</td>
                      <td className="num">−{v.points_removed}</td>
                      <td className="num">{v.total_after}</td>
                      <td className="num">{new Date(v.created_at).toLocaleString()}</td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => void onRollback(v.version_no)}>
                          Roll back
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'alert-rules' && <AlertRulesPanel datasetId={datasetId} />}
    </div>
  )
}
