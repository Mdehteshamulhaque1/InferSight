import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion, useInView } from 'framer-motion'
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  Brain,
  ChevronDown,
  ChevronRight,
  Cpu,
  Database,
  Factory,
  FileText,
  GraduationCap,
  HeartPulse,
  Landmark,
  LayoutDashboard,
  Lightbulb,
  LineChart,
  Lock,
  Menu,
  MessageSquare,
  Moon,
  Plug,
  Radar,
  Rocket,
  Scale,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Sun,
  TrendingUp,
  Truck,
  Wallet,
  Workflow,
  X,
  Zap,
} from 'lucide-react'
import { useAuth } from '../app/providers/AuthContext'
import { LandingChat } from '../components/features/chat/LandingChat'
import { usePageTitle } from '../hooks/usePageTitle'
import '../styles/landing.css'

const REV = [42, 48, 44, 53, 50, 58, 64, 61, 70, 74, 71, 80, 86, 83, 92, 97, 95, 104, 110, 107, 116]

function pts(data: number[], W: number, H: number, P: number): [number, number][] {
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  return data.map((v, i) => [
    P + (i / (data.length - 1)) * (W - P * 2),
    H - P - ((v - min) / span) * (H - P * 2),
  ])
}

function pathOf(points: [number, number][]): string {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
}

function LogoMark() {
  return (
    <svg width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="ldlg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#3b82f6" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#ldlg)" />
      <path d="M7 21l5-6 4 4 6-8" stroke="#fff" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="23.5" cy="11.5" r="1.8" fill="#fff" />
    </svg>
  )
}

function Fade({ children, delay = 0, y = 26 }: { children: ReactNode; delay?: number; y?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.6, delay, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}

function CountUp({
  value,
  decimals = 0,
  prefix = '',
  suffix = '',
}: {
  value: number
  decimals?: number
  prefix?: string
  suffix?: string
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '-40px' })
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    if (!inView) return
    const t0 = performance.now()
    let raf = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / 1400)
      setDisplay(value * (1 - Math.pow(1 - p, 3)))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [inView, value])
  return (
    <span ref={ref}>
      {prefix}
      {display.toFixed(decimals)}
      {suffix}
    </span>
  )
}

function SectionHead({
  eyebrow,
  title,
  sub,
  center = false,
}: {
  eyebrow: string
  title: ReactNode
  sub?: string
  center?: boolean
}) {
  return (
    <div className={`ld-section-head${center ? ' center' : ''}`}>
      <span className="ld-eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      {sub && <p>{sub}</p>}
    </div>
  )
}

function HeroChart() {
  const W = 600
  const H = 212
  const P = 14
  const line = pts(REV, W, H, P)
  const last = line[line.length - 1]
  const ai = line[15]
  const area = `${pathOf(line)} L${last[0].toFixed(1)},${H - P} L${line[0][0].toFixed(1)},${H - P} Z`
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Revenue trend with forecast extension and anomaly dot">
      <defs>
        <linearGradient id="ldhc" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2563eb" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#2563eb" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((f) => (
        <line key={f} x1={P} x2={W - P} y1={P + f * (H - P * 2)} y2={P + f * (H - P * 2)} stroke="var(--l-line)" strokeWidth="1" />
      ))}
      <path d={area} fill="url(#ldhc)" />
      <path
        d={`${pathOf(line)} M${ai[0].toFixed(1)},${ai[1].toFixed(1)} L${W - P},${ai[1].toFixed(1)}`}
        fill="none"
        stroke="#2563eb"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d={`M${ai[0].toFixed(1)},${ai[1].toFixed(1)} L${W - P},${ai[1].toFixed(1)}`}
        fill="none"
        stroke="#38bdf8"
        strokeWidth="2"
        strokeDasharray="5 5"
        strokeLinecap="round"
      />
      <circle cx={ai[0]} cy={ai[1]} r="5" fill="#f59e0b" stroke="#fff" strokeWidth="2" />
      <circle cx={ai[0]} cy={ai[1]} r="11" fill="none" stroke="#f59e0b" strokeWidth="1.5" opacity="0.5" />
    </svg>
  )
}

function SparkLine({ data, color }: { data: number[]; color: string }) {
  const W = 260
  const H = 64
  const P = 4
  const p = pts(data, W, H, P)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      <path d={pathOf(p)} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const FEATURES: { icon: typeof Sparkles; title: string; desc: string }[] = [
  { icon: Sparkles, title: 'AI Insights', desc: 'Automatically written explanations and next-step recommendations for every metric.' },
  { icon: Activity, title: 'Real-time Analytics', desc: 'Score every incoming point against a rolling baseline the moment it lands.' },
  { icon: TrendingUp, title: 'Predictive Forecasting', desc: 'Linear, exponential, and Holt models fit with holdout scoring and confidence bands.' },
  { icon: LayoutDashboard, title: 'Custom Dashboards', desc: 'Assemble KPIs, charts, and health rings into shareable views in minutes.' },
  { icon: Radar, title: 'Anomaly Detection', desc: 'Spikes, drops, and plateaus flagged with severity, direction, and a reason.' },
  { icon: MessageSquare, title: 'Natural Language Queries', desc: 'Ask your data plain questions — get charts, numbers, and answers back.' },
  { icon: FileText, title: 'Automated Reports', desc: 'One-click CSV, XLSX, and PDF exports of datasets, forecasts, and anomaly runs.' },
  { icon: Lightbulb, title: 'Smart Recommendations', desc: 'The assistant suggests the next metric, filter, or action worth your attention.' },
  { icon: Lock, title: 'Role-Based Access', desc: 'Granular roles and permissions so the right people see the right data.' },
  { icon: Plug, title: 'API Integration', desc: 'REST API and webhooks plug InferSight into your existing stack in minutes.' },
  { icon: Workflow, title: 'Workflow Automation', desc: 'Rules route findings to email, Slack, and webhooks — with self-escalation.' },
  { icon: ShieldCheck, title: 'Data Security', desc: 'Encrypted at rest and in transit, with audit logs on every action.' },
]

const SOLUTIONS: { icon: typeof Wallet; title: string; desc: string }[] = [
  { icon: Wallet, title: 'Finance', desc: 'Revenue, burn, and risk in one view' },
  { icon: HeartPulse, title: 'Healthcare', desc: 'Operational and clinical KPIs' },
  { icon: ShoppingBag, title: 'Retail', desc: 'Demand, churn, and promotions' },
  { icon: Factory, title: 'Manufacturing', desc: 'Yield, downtime, and throughput' },
  { icon: GraduationCap, title: 'Education', desc: 'Enrollment and retention trends' },
  { icon: Truck, title: 'Logistics', desc: 'Delivery and fleet performance' },
  { icon: Landmark, title: 'Banking', desc: 'Fraud signals and portfolio health' },
  { icon: Scale, title: 'Government', desc: 'Public-service metrics and SLAs' },
]

const FAQ = [
  { q: 'How fast can I connect my data?', a: 'Upload a CSV or call our REST API and InferSight normalizes it automatically. Most teams get their first anomaly scored and explained in under a minute.' },
  { q: 'How accurate are the forecasts?', a: 'We fit multiple models — linear, exponential, and Holt — and score them against a holdout window, surfacing the best fit with confidence bands. Typical error sits in the low single digits.' },
  { q: 'Does the AI assistant need a model API key?', a: 'No. The core explanations are generated by a deterministic engine. If you configure an LLM provider, answers get richer — but everything works out of the box without one.' },
  { q: 'Can I get alerts in Slack or on email?', a: 'Yes. Build rules per dataset with cooldowns and severity thresholds, then route them to email, Slack, or any webhook. Critical, unacknowledged alerts can escalate automatically.' },
  { q: 'What does Enterprise include?', a: 'SSO, role-based access, dedicated infrastructure, audit logs, SLAs, and hands-on onboarding. Contact us for a scoped rollout plan.' },
]

const NAV = [
  { label: 'Features', href: '#features' },
  { label: 'Solutions', href: '#solutions' },
  { label: 'AI', href: '#ai' },
  { label: 'Resources', href: '#resources' },
]

const MEGA_COLS = [
  { head: 'By industry', links: ['Finance', 'Healthcare', 'Retail', 'Manufacturing'] },
  { head: 'By role', links: ['Data analysts', 'Executives', 'Engineers', 'Operations'] },
]

export function Landing() {
  const { user } = useAuth()
  usePageTitle('')
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [openFaq, setOpenFaq] = useState<number | null>(0)
  const [dark, setDark] = useState(() => {
    if (typeof localStorage === 'undefined') return false
    return localStorage.getItem('ld-theme') === 'dark'
  })

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    localStorage.setItem('ld-theme', dark ? 'dark' : 'light')
  }, [dark])

  const go = user ? '/app/home' : '/login'

  return (
    <div className={`landing${dark ? ' ld-dark' : ''}`} id="top">
      <nav className={`ld-nav${scrolled ? ' scrolled' : ''}`} aria-label="Primary">
        <a className="ld-logo" href="#top">
          <LogoMark />
          <span className="word">InferSight</span>
        </a>
        <div className="ld-nav-links">
          {NAV.map((n) =>
            n.label === 'Solutions' ? (
              <div className="ld-mega" key={n.label}>
                <span className="ld-nav-link ld-mega-trigger">
                  {n.label} <ChevronDown size={14} />
                </span>
                <div className="ld-mega-panel">
                  {MEGA_COLS.map((col) => (
                    <div className="ld-mega-col" key={col.head}>
                      <h6>{col.head}</h6>
                      {col.links.map((l) => (
                        <a href="#solutions" key={l}>
                          {l}
                        </a>
                      ))}
                    </div>
                  ))}
                  <div className="ld-mega-feat">
                    <Bot size={20} />
                    <b>AI Copilot</b>
                    <span>Ask questions about your data and get charts and answers instantly.</span>
                    <a href="#ai">
                      Explore the assistant <ArrowRight size={13} />
                    </a>
                  </div>
                </div>
              </div>
            ) : (
              <a className="ld-nav-link" href={n.href} key={n.label}>
                {n.label}
              </a>
            )
          )}
        </div>
        <div className="ld-nav-actions">
          <button
            type="button"
            className="ld-theme-btn"
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            onClick={() => setDark((d) => !d)}
          >
            {dark ? <Sun size={17} /> : <Moon size={17} />}
          </button>
          {!user && (
            <Link className="ld-btn ld-btn-ghost ld-btn-sm" to="/login">
              Login
            </Link>
          )}
          <Link className="ld-btn ld-btn-primary ld-btn-sm" to={go}>
            Get started <ArrowRight size={15} />
          </Link>
          <button type="button" className="ld-btn ld-btn-glass ld-menu-btn" aria-label="Menu" onClick={() => setMenuOpen((o) => !o)}>
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </nav>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            className="ld-mobile-menu"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            {NAV.map((n) => (
              <a href={n.href} key={n.label} onClick={() => setMenuOpen(false)}>
                {n.label}
              </a>
            ))}
            {!user && (
              <a href="/login" onClick={() => setMenuOpen(false)}>
                Login
              </a>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ---- Hero ---- */}
      <header className="ld-hero">
        <div className="ld-orbs" aria-hidden="true">
          <span className="ld-orb o1" />
          <span className="ld-orb o2" />
          <span className="ld-orb o3" />
        </div>
        <div className="ld-hero-inner">
          <span className="ld-badge">
            <span className="pulse-dot" aria-hidden="true" />
            AI-Powered Business Intelligence &amp; Decision Platform
          </span>
          <h1>
            Transform business data into <span className="grad">intelligent decisions.</span>
          </h1>
          <p className="sub">
            InferSight scores every point for anomalies, forecasts what's next with confidence
            bands, and writes the explanation — all in one enterprise platform.
          </p>
          <div className="ld-hero-cta">
            <Link className="ld-btn ld-btn-primary ld-btn-lg" to={go}>
              Get started <ArrowRight size={18} />
            </Link>
          </div>
        </div>

        <div className="ld-hero-visual">
          <motion.div
            className="ld-hv-card"
            initial={{ opacity: 0, y: 30, rotateY: -8 }}
            animate={{ opacity: 1, y: 0, rotateY: -6 }}
            transition={{ duration: 0.8, delay: 0.2, ease: 'easeOut' }}
          >
            <div className="ld-hv-kpis">
              <div className="ld-hv-kpi">
                <div className="l">Revenue</div>
                <b>$42.8k</b>
              </div>
              <div className="ld-hv-kpi">
                <div className="l">Trend</div>
                <b className="up">+12.4%</b>
              </div>
              <div className="ld-hv-kpi">
                <div className="l">Health</div>
                <b className="health">94</b>
              </div>
            </div>
            <div className="ld-hv-chart">
              <HeroChart />
            </div>
            <div className="ld-hv-rows">
              <div className="ld-hv-row">
                <Sparkles size={14} />
                Revenue growth is accelerating; forecast to $51k next period.
                <span className="tag ai">AI</span>
              </div>
              <div className="ld-hv-row">
                <Activity size={14} />
                4.2σ spike detected · Jan 23 · expected $41.9k
                <span className="tag al">ALERT</span>
              </div>
            </div>
          </motion.div>

          <motion.div
            className="ld-glass-card float-a"
            animate={{ y: [0, -12, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
          >
            <div className="lbl">Forecast</div>
            <div className="val">
              $51.2k <span className="chg good">+19%</span>
            </div>
          </motion.div>

          <motion.div
            className="ld-glass-card float-b"
            animate={{ y: [0, 12, 0] }}
            transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut', delay: 1.2 }}
          >
            <div className="lbl">Risk score</div>
            <div className="ring">92</div>
          </motion.div>
        </div>
      </header>

      {/* ---- Features ---- */}
      <section className="ld-section" id="features">
        <SectionHead
          eyebrow="Platform"
          title={<>Everything you need to understand your metrics.</>}
          sub="Twelve capabilities, one pipeline — from raw series to explanation, alert, and action."
        />
        <div className="ld-feature-grid">
          {FEATURES.map((f, i) => {
            const Icon = f.icon
            return (
              <Fade delay={(i % 3) * 0.06} key={f.title}>
                <div className="ld-feature-card">
                  <span className="ico">
                    <Icon size={20} />
                  </span>
                  <h3>{f.title}</h3>
                  <p>{f.desc}</p>
                </div>
              </Fade>
            )
          })}
        </div>
      </section>

      {/* ---- AI Assistant ---- */}
      <section className="ld-section" id="ai">
        <div className="ld-ai">
          <div className="ld-ai-copy">
            <Fade>
              <SectionHead
                eyebrow="AI Assistant"
                title={<>Ask your data anything. <span className="grad" style={{ background: 'var(--l-grad)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Get answers.</span></>}
                sub="A deterministic engine plus optional LLM enrichment turns plain questions into charts, numbers, and plain-English explanations."
              />
              <div className="ld-ai-bullets">
                {[
                  { icon: Brain, t: 'Understands business questions', d: '“What caused revenue to drop last month?” becomes a structured analysis.' },
                  { icon: LineChart, t: 'Answers with evidence', d: 'Every claim is backed by the exact series, models, and numbers behind it.' },
                  { icon: Zap, t: 'Works without an LLM key', d: 'Core explanations are generated locally and deterministically.' },
                ].map((b) => {
                  const Icon = b.icon
                  return (
                    <div className="ld-ai-bullet" key={b.t}>
                      <span className="ico">
                        <Icon size={16} />
                      </span>
                      <div>
                        <b>{b.t}</b>
                        <span>{b.d}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
              <Link className="ld-btn ld-btn-primary" to={go}>
                Try the assistant <ArrowRight size={16} />
              </Link>
            </Fade>
          </div>

          <Fade delay={0.1}>
            <div className="ld-ai-chat">
              <div className="ld-ai-msg q">What caused revenue to drop last month?</div>
              <div className="ld-ai-msg a">
                Revenue fell 8.2% in June, driven mainly by a checkout failure on the payment
                gateway between Jun 14–17 (−$214k), plus slower enterprise renewal timing.
                <div className="m-chart">
                  <SparkLine data={[38, 40, 39, 36, 33, 35, 41, 43, 45]} color="var(--l-secondary)" />
                </div>
              </div>
              <span className="ld-ai-chip">Ask a follow-up · “Which region was affected?”</span>
              <div className="ld-ai-msg a">
                EMEA accounted for 62% of the drop. A recommended rerun of the payment
                integration resolved 91% of the failed transactions within 48 hours.
              </div>
            </div>
          </Fade>
        </div>
      </section>

      {/* ---- Interactive dashboard preview ---- */}
      <section className="ld-section" id="solutions">
        <SectionHead
          eyebrow="Interactive dashboard"
          title={<>Your metrics, live.</>}
          sub="KPI monitoring, forecasting, and traffic heatmaps — in one clean workspace."
          center
        />
        <Fade y={40}>
          <div className="ld-dashboard">
            <div className="ld-dash-stats">
              {[
                { l: 'Revenue', v: <CountUp value={2.4} decimals={1} prefix="$" suffix="M" />, c: '+18.2%', good: true },
                { l: 'Users', v: <CountUp value={48.2} decimals={1} suffix="K" />, c: '+6.4%', good: true },
                { l: 'Orders', v: <CountUp value={1208} />, c: '+12.1%', good: true },
                { l: 'Traffic', v: <CountUp value={318} suffix="K" />, c: '+9.8%', good: true },
                { l: 'Conversion', v: <CountUp value={3.9} decimals={1} suffix="%" />, c: '+0.4pt', good: true },
                { l: 'Forecast', v: <CountUp value={2.9} decimals={1} prefix="$" suffix="M" />, c: '+21%', good: true },
              ].map((s) => (
                <div className="ld-dash-stat" key={s.l}>
                  <div className="l">{s.l}</div>
                  <b>{s.v}</b>
                  <span className={`c ${s.good ? 'good' : 'bad'}`}>{s.c}</span>
                </div>
              ))}
            </div>
            <div className="ld-dash-body">
              <div className="ld-panel">
                <div className="pt">
                  Revenue forecast <span className="lg">Holt-Winters · 30d</span>
                </div>
                <HeroChart />
              </div>
              <div className="ld-panel">
                <div className="pt">
                  Traffic heatmap <span className="lg">7d × 10 slots</span>
                </div>
                <div className="ld-heat">
                  {Array.from({ length: 70 }, (_, i) => {
                    const a = 0.08 + ((i * 7 + Math.floor(i / 7) * 3) % 9) / 11
                    return <i key={i} style={{ background: `rgba(37, 99, 235, ${a})` }} />
                  })}
                </div>
              </div>
            </div>
          </div>
        </Fade>
      </section>

      {/* ---- Workflow ---- */}
      <section className="ld-section" id="workflow">
        <SectionHead
          eyebrow="Workflow"
          title={<>From raw data to action — in five steps.</>}
          sub="A pipeline that runs without babysitting."
          center
        />
        <div className="ld-flow">
          <span className="ld-flow-line" aria-hidden="true" />
          {[
            { icon: Database, t: 'Connect Data', d: 'CSV, stream, or API' },
            { icon: BarChart3, t: 'Analyze', d: 'Baseline + score every point' },
            { icon: Cpu, t: 'Predict', d: 'Models with confidence bands' },
            { icon: Lightbulb, t: 'Recommend', d: 'Written next steps' },
            { icon: Rocket, t: 'Take Action', d: 'Alerts, reports, automation' },
          ].map((s, i) => {
            const Icon = s.icon
            return (
              <Fade delay={i * 0.08} key={s.t}>
                <div className="ld-flow-step">
                  <span className="ld-flow-ico">
                    <Icon size={24} />
                  </span>
                  <h4>{s.t}</h4>
                  <p>{s.d}</p>
                </div>
              </Fade>
            )
          })}
          {[1, 2, 3, 4].map((i) => (
            <ChevronRight key={i} className="ld-flow-arrow" size={22} style={{ left: `${i * 20}%` }} />
          ))}
        </div>
      </section>

      {/* ---- Business solutions ---- */}
      <section className="ld-section" id="industries">
        <SectionHead
          eyebrow="Business solutions"
          title={<>Built for every industry.</>}
          sub="The same engine, tuned to the metrics that matter to you."
        />
        <div className="ld-sol-grid">
          {SOLUTIONS.map((s, i) => {
            const Icon = s.icon
            return (
              <Fade delay={(i % 4) * 0.06} key={s.title}>
                <div className="ld-sol-card">
                  <span className="ico">
                    <Icon size={19} />
                  </span>
                  <div>
                    <b>{s.title}</b>
                    <span>{s.desc}</span>
                  </div>
                </div>
              </Fade>
            )
          })}
        </div>
      </section>

      {/* ---- FAQ ---- */}
      <section className="ld-section" id="faq">
        <SectionHead eyebrow="FAQ" title="Frequently asked questions" center />
        <div className="ld-faq">
          {FAQ.map((f, i) => (
            <div className={`ld-faq-item${openFaq === i ? ' open' : ''}`} key={f.q}>
              <button type="button" className="ld-faq-q" onClick={() => setOpenFaq(openFaq === i ? null : i)} aria-expanded={openFaq === i}>
                {f.q}
                <ChevronDown size={18} />
              </button>
              <AnimatePresence initial={false}>
                {openFaq === i && (
                  <motion.div
                    key="a"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.24, ease: 'easeOut' }}
                    style={{ overflow: 'hidden' }}
                  >
                    <div className="ld-faq-a">{f.a}</div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </section>

      {/* ---- CTA ---- */}
      <section className="ld-section" id="cta">
        <motion.div
          className="ld-cta-inner"
          initial={{ opacity: 0, scale: 0.97 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        >
          <span className="orb c1" aria-hidden="true" />
          <span className="orb c2" aria-hidden="true" />
          <h2>Ready to make smarter decisions?</h2>
          <p>Connect your first dataset and get an AI-written explanation of your metrics — in under a minute.</p>
          <div className="ld-cta-row">
            <Link className="ld-btn ld-btn-white ld-btn-lg" to={go}>
              Explore the platform <ArrowRight size={18} />
            </Link>
          </div>
        </motion.div>
      </section>

      {/* ---- Footer ---- */}
      <footer className="ld-footer" id="resources">
        <div className="ld-foot-grid">
          <div className="ld-foot-brand">
            <a className="ld-logo" href="#top">
              <LogoMark />
              <span className="word">InferSight</span>
            </a>
            <p>AI-powered business intelligence for teams that want answers, not dashboards to babysit.</p>
          </div>
          <div className="ld-foot-col">
            <h5>Product</h5>
            <Link to="/app/home">Copilot</Link>
            <Link to="/app/dashboard">Dashboard</Link>
            <Link to="/app/datasets">Datasets</Link>
            <Link to="/app/insights">Insights</Link>
            <Link to="/app/alerts">Alerts</Link>
            <Link to="/app/reports">Reports</Link>
          </div>
          <div className="ld-foot-col">
            <h5>Solutions</h5>
            <a href="#industries">Finance</a>
            <a href="#industries">Healthcare</a>
            <a href="#industries">Retail</a>
            <a href="#industries">Logistics</a>
            <a href="#industries">Government</a>
          </div>
          <div className="ld-foot-col">
            <h5>Developers</h5>
            <Link to="/app/upload">REST API</Link>
            <Link to="/app/alerts">Webhooks</Link>
            <Link to="/app/datasets">Data models</Link>
            <Link to="/app/upload">Integrations</Link>
          </div>
          <div className="ld-foot-col">
            <h5>Resources</h5>
            <a href="#faq">FAQ</a>
            <a href="#workflow">How it works</a>
            <a href="#ai">AI assistant</a>
          </div>
        </div>
        <div className="ld-foot-bottom">
          <span>© {new Date().getFullYear()} InferSight</span>
          <span>Privacy · Terms · Security</span>
          <span>FastAPI · React · PostgreSQL · Redis</span>
        </div>
      </footer>

      <LandingChat />
    </div>
  )
}
