import { useEffect, useMemo, useState } from 'react'
import type { ComponentType } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../app/providers/AuthContext'
import { LandingChat } from '../components/features/chat/LandingChat'
import { usePageTitle } from '../hooks/usePageTitle'
import type { Anomaly, SeriesPoint } from '../types'
import type { IconProps } from '../components/ui/icons'
import {
  IconActivity,
  IconArrowRight,
  IconBell,
  IconDatabase,
  IconDownload,
  IconHealth,
  IconSpark,
  IconSparkles,
  IconTrend,
  IconUpload,
} from '../components/ui/icons'

function sampleSeries(days: number, base: number): { series: SeriesPoint[]; anomalies: Anomaly[] } {
  const series: SeriesPoint[] = []
  const anomalies: Anomaly[] = []
  const start = new Date(Date.UTC(2026, 0, 1))
  for (let i = 0; i < days; i++) {
    const clean = base + i * 55 + Math.sin(i / 6) * 900 + (i % 7 === 2 ? 320 : 0) + ((i * 7919) % 17)
    const ts = new Date(start.getTime() + i * 86_400_000).toISOString()
    if (i === 22) {
      anomalies.push({
        timestamp: ts,
        value: clean + 4200,
        expected: clean,
        score: 4.2,
        severity: 'critical',
        direction: 'spike',
        reason: 'value deviates sharply above expected level',
      })
    }
    series.push({ timestamp: ts, value: Math.round(clean) })
  }
  return { series, anomalies }
}

function LogoMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path
        d="M3 21l6-5 4 4 7-9 7 7"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M25 8h4v4" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="26.5" cy="9.5" r="2" fill="var(--amber)" stroke="none" />
    </svg>
  )
}

function Trace() {
  const { series, anomalies } = useMemo(() => sampleSeries(42, 900), [])
  const W = 840
  const H = 260
  const PAD_X = 18
  const PAD_Y = 20
  const values = series.map((p) => p.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const x = (i: number) => PAD_X + (i / (series.length - 1)) * (W - PAD_X * 2)
  const y = (v: number) => H - PAD_Y - ((v - min) / span) * (H - PAD_Y * 2)
  const line = series
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`)
    .join(' ')
  const baseY = H - PAD_Y
  const area = `${line} L${x(series.length - 1).toFixed(1)},${baseY} L${x(0).toFixed(1)},${baseY} Z`
  const anomaly = anomalies[0]
  const ai = anomaly ? series.findIndex((p) => p.timestamp === anomaly.timestamp) : -1
  const ax = ai >= 0 ? x(ai) : null
  const ay = anomaly ? y(anomaly.value) : null

  return (
    <svg className="ld-trace" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Anomaly trace with a detected spike">
      {[0.25, 0.5, 0.75].map((f) => (
        <line key={f} className="ld-trace-grid" x1={PAD_X} x2={W - PAD_X} y1={baseY - f * (H - PAD_Y * 2)} y2={baseY - f * (H - PAD_Y * 2)} />
      ))}
      <path className="ld-trace-area" d={area} />
      <path className="ld-trace-line" d={line} pathLength={1} />
      {ax != null && ay != null && anomaly && (
        <g className="ld-trace-dot">
          <line
            className="ld-trace-expected"
            x1={x(Math.max(0, ai - 4))}
            x2={x(Math.min(series.length - 1, ai + 4))}
            y1={y(anomaly.expected)}
            y2={y(anomaly.expected)}
          />
          <circle className="ring" cx={ax} cy={ay} r={7} />
          <circle cx={ax} cy={ay} r={4.5} fill="var(--amber)" stroke="none" />
        </g>
      )}
    </svg>
  )
}

const TICKER = [
  'Anomaly detection',
  'Forecasting',
  'Written insights',
  'Root-cause correlation',
  'Alert routing',
  'Health scores',
  'KPI discovery',
  'CSV · XLSX · PDF exports',
]

const FEATURES: { icon: ComponentType<IconProps>; title: string; desc: string }[] = [
  {
    icon: IconActivity,
    title: 'Anomaly detection',
    desc: 'Every point is scored against a rolling z-score baseline. Spikes and drops are flagged with severity, direction, and a plain-English reason.',
  },
  {
    icon: IconTrend,
    title: 'Forecasting',
    desc: 'Linear, exponential, and Holt models are fit with holdout scoring and projected forward inside confidence bands.',
  },
  {
    icon: IconSparkles,
    title: 'Written insights',
    desc: 'A deterministic engine writes summaries and next-step recommendations — with optional LLM enrichment when a provider is configured.',
  },
  {
    icon: IconDatabase,
    title: 'Related signals',
    desc: 'Each anomaly is correlated against every sibling dataset in your organization to surface what moved together — and what moved against it.',
  },
  {
    icon: IconHealth,
    title: 'Health scores',
    desc: 'A composable score grades each metric on stability, trend, and anomalies, with an actionable checklist.',
  },
  {
    icon: IconBell,
    title: 'Alert routing & escalation',
    desc: 'Rule-based delivery over email, Slack, and webhooks with per-rule cooldowns — plus automatic escalation of critical, unacknowledged alerts.',
  },
]

const PRODUCTS: {
  icon: ComponentType<IconProps>
  tag: string
  title: string
  desc: string
  to: string
}[] = [
  {
    icon: IconActivity,
    tag: 'Core',
    title: 'Anomaly detection',
    desc: 'Rolling z-score scoring on every point, with severity, direction, and a plain-English reason.',
    to: '/app/dashboard',
  },
  {
    icon: IconTrend,
    tag: 'Forecast',
    title: 'Forecasting',
    desc: 'Linear, exponential, and Holt models fit with holdout scoring and confidence bands.',
    to: '/app/dashboard',
  },
  {
    icon: IconSparkles,
    tag: 'Written',
    title: 'Insights',
    desc: 'Summaries and next-step recommendations written automatically — no prompts required.',
    to: '/app/insights',
  },
  {
    icon: IconBell,
    tag: 'Routing',
    title: 'Alerting',
    desc: 'Email, Slack, and webhooks with per-rule cooldowns and self-escalating criticals.',
    to: '/app/alerts',
  },
  {
    icon: IconDownload,
    tag: 'Export',
    title: 'Reports',
    desc: 'One-click CSV, XLSX, and PDF exports of datasets, forecasts, and anomaly runs.',
    to: '/app/datasets',
  },
  {
    icon: IconHealth,
    tag: 'Grade',
    title: 'Health scores',
    desc: 'A composable score grades stability, trend, and anomalies with an actionable checklist.',
    to: '/app/dashboard',
  },
]

const STEPS: { num: string; icon: ComponentType<IconProps>; title: string; desc: string }[] = [
  {
    num: '01',
    icon: IconUpload,
    title: 'Ingest',
    desc: 'Drop a CSV, connect a stream, or point at a sibling dataset. The pipeline normalizes it automatically.',
  },
  {
    num: '02',
    icon: IconSpark,
    title: 'Score',
    desc: 'Every point is scored against a rolling baseline. Spikes, drops, and plateaus are flagged with severity.',
  },
  {
    num: '03',
    icon: IconDatabase,
    title: 'Correlate',
    desc: 'Each anomaly is matched against every sibling dataset to surface what moved together — and what fought it.',
  },
  {
    num: '04',
    icon: IconBell,
    title: 'Route',
    desc: 'Critical findings escalate on their own while routine ones wait for review. You approve, not babysit.',
  },
]

const STATS: { value: string; label: string }[] = [
  { value: '3.2M', label: 'points scored every week' },
  { value: '4', label: 'forecast models per dataset' },
  { value: '6', label: 'delivery channels for alerts' },
  { value: '0', label: 'hand-written explanations' },
]

export function Landing() {
  const { user } = useAuth()
  usePageTitle('')
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="landing" id="top">
      <div className="ld-bar">
        <span>Open beta — free for teams under 3 seats</span>
        <a href="#join">
          Claim your seat <IconArrowRight size={12} />
        </a>
      </div>
      <nav className={`ld-nav${scrolled ? ' scrolled' : ''}`} aria-label="Primary">
        <a className="ld-logo" href="#top">
          <LogoMark />
          <span className="word">InferSight</span>
        </a>
        <div className="ld-links">
          <a href="#features">Platform</a>
          <a href="#products">Products</a>
          <a href="#how">How it runs</a>
          <a href="#stats">Numbers</a>
        </div>
        <div className="ld-actions">
          {user ? (
            <Link className="btn-amber" to="/app/dashboard">
              Open dashboard <IconArrowRight size={14} />
            </Link>
          ) : (
            <>
              <Link className="btn-ghost" to="/login">
                Sign in
              </Link>
              <Link className="btn-amber" to="/register">
                Get started <IconArrowRight size={14} />
              </Link>
            </>
          )}
        </div>
      </nav>

      <header className="ld-hero">
        <div className="ld-orbs" aria-hidden="true">
          <span className="ld-orb amber" />
          <span className="ld-orb teal" />
        </div>
        <div className="ld-hero-inner">
          <span className="ld-badge ld-fade" style={{ animationDelay: '0ms' }}>
            <span className="dot" aria-hidden="true" />
            Anomaly detection · forecasts · written insights
          </span>
          <h1 className="ld-fade" style={{ animationDelay: '150ms' }}>
            Turn raw metrics into <span className="accent">decisions.</span>
          </h1>
          <p className="lead ld-fade" style={{ animationDelay: '300ms' }}>
            InferSight scores every point in your time series for anomalies, forecasts what's
            next with confidence bands, and writes the explanation — automatically.
          </p>
          <div className="ld-cta-row ld-fade" style={{ animationDelay: '450ms' }}>
            <Link className="btn-amber" to={user ? '/app/dashboard' : '/register'}>
              {user ? 'Open dashboard' : 'Start free'} <IconArrowRight size={15} />
            </Link>
            {!user && (
              <Link className="btn-ghost" to="/login">
                Sign in
              </Link>
            )}
          </div>
        </div>

        <div className="ld-preview ld-fade" style={{ animationDelay: '600ms' }}>
          <div className="bar">
            <div className="dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
            <span className="addr">app.infersight.dev/datasets/daily-revenue</span>
          </div>
          <div className="body">
            <div className="kpis">
              <div className="kpi">
                <div className="l">Revenue</div>
                <b>$42.8k</b>
              </div>
              <div className="kpi">
                <div className="l">Trend</div>
                <b className="up">+12.4%</b>
              </div>
              <div className="kpi">
                <div className="l">Anomalies</div>
                <b className="bad">1</b>
              </div>
            </div>
            <Trace />
            <div className="flag">
              <span className="dot" />
              Anomaly flagged · Jan 23 · 4.2σ spike
            </div>
          </div>
        </div>
      </header>

      <div className="ld-ticker" aria-hidden="true">
        <div className="ld-ticker-track">
          {[...TICKER, ...TICKER].map((item, i) => (
            <span key={i}>{item}</span>
          ))}
        </div>
      </div>

      <section className="ld-features" id="features">
        <div className="ld-section-head">
          <span className="ld-eyebrow">Platform</span>
          <h2>Built for continuous monitoring.</h2>
          <p>One pipeline from raw series to explanation, alert, and action.</p>
        </div>
        {FEATURES.map((f, i) => (
          <div className="ld-feature" key={f.title}>
            <div className="idx">{String(i + 1).padStart(2, '0')}</div>
            <div className="cnt">
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
            <f.icon className="glyph" size={22} />
          </div>
        ))}
      </section>

      <section className="ld-statement">
        <span className="ld-eyebrow">The thesis</span>
        <p className="ld-statement-line">
          Your metrics are talking.
          <br />
          <em>We make sure you hear them.</em>
        </p>
        <p className="ld-statement-sub">
          InferSight scores every point, correlates every spike, and writes the explanation —
          so your team acts on the signal, not the dashboard.
        </p>
      </section>

      <section className="ld-products" id="products">
        <div className="ld-section-head">
          <span className="ld-eyebrow">Platform</span>
          <h2>Pick your weapon.</h2>
          <p>Six modules. One pipeline. No setup gymnastics.</p>
        </div>
        <div className="ld-product-grid">
          {PRODUCTS.map((p) => (
            <Link className="ld-product" to={p.to} key={p.title}>
              <div className="top">
                <p.icon className="glyph" size={22} />
                <span className="tag">{p.tag}</span>
              </div>
              <h3>{p.title}</h3>
              <p>{p.desc}</p>
              <span className="go">
                Explore <IconArrowRight size={13} />
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section className="ld-cats">
        <Link className="ld-cat ink" to="/app/datasets">
          <span className="ld-eyebrow">Start here</span>
          <h3>
            Bring the data.
            <br />
            We do the rest.
          </h3>
          <span className="go">
            Explore datasets <IconArrowRight size={14} />
          </span>
        </Link>
        <Link className="ld-cat amber" to="/app/alerts">
          <span className="ld-eyebrow">Always on</span>
          <h3>
            Alerts that
            <br />
            escalate themselves.
          </h3>
          <span className="go">
            Explore alerts <IconArrowRight size={14} />
          </span>
        </Link>
      </section>

      <section className="ld-how" id="how">
        <div className="ld-section-head">
          <span className="ld-eyebrow">How it runs</span>
          <h2>From raw to routed.</h2>
          <p>Four steps. Zero babysitting.</p>
        </div>
        <div className="ld-steps">
          {STEPS.map((s) => (
            <div className="ld-step" key={s.num}>
              <div className="num">{s.num}</div>
              <s.icon className="glyph" size={20} />
              <h4>{s.title}</h4>
              <p>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="ld-stats" id="stats">
        {STATS.map((s) => (
          <div className="stat" key={s.label}>
            <b>{s.value}</b>
            <span>{s.label}</span>
          </div>
        ))}
      </section>

      <section className="ld-join" id="join">
        <div className="inner">
          <span className="ld-eyebrow">Open beta</span>
          <h2>Your metrics are talking.</h2>
          <p>Create a team, upload a CSV, and get your first explanation in under a minute.</p>
          <div className="ld-cta-row">
            <Link className="btn-ink" to={user ? '/app/dashboard' : '/register'}>
              {user ? 'Open dashboard' : 'Start free'} <IconArrowRight size={15} />
            </Link>
            {!user && (
              <Link className="btn-ghost" to="/login">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </section>

      <footer className="ld-footer">
        <div className="cols">
          <div>
            <h4>Product</h4>
            <Link to="/app/dashboard">Dashboard</Link>
            <Link to="/app/datasets">Datasets</Link>
            <Link to="/app/insights">Insights</Link>
            <Link to="/app/alerts">Alerts</Link>
          </div>
          <div>
            <h4>Platform</h4>
            <a href="#products">Anomaly detection</a>
            <a href="#products">Forecasting</a>
            <a href="#products">Written insights</a>
            <a href="#products">Related signals</a>
          </div>
          <div>
            <h4>How it works</h4>
            <a href="#how">Ingest</a>
            <a href="#how">Score</a>
            <a href="#how">Correlate</a>
            <a href="#how">Route</a>
          </div>
          <div>
            <h4>Project</h4>
            <a href="#features">Documentation</a>
            <a href="#stats">Numbers</a>
            <Link to="/login">Sign in</Link>
            <Link to="/register">Create account</Link>
          </div>
        </div>
        <div className="bottom">
          <span>© {new Date().getFullYear()} InferSight</span>
          <span>FastAPI · React · PostgreSQL · Redis</span>
        </div>
      </footer>

      <LandingChat />
    </div>
  )
}
