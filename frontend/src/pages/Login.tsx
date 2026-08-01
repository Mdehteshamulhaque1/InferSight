import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../app/providers/AuthContext'
import { Mesh } from '../components/ui/Mesh'
import { useToast } from '../components/ui/Toast'
import { usePageTitle } from '../hooks/usePageTitle'
import { IconCheck, IconEye, IconEyeOff, IconTrend } from '../components/ui/icons'

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  usePageTitle('Sign in')
  const [email, setEmail] = useState('demo@infersight.dev')
  const [password, setPassword] = useState('demo12345')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      toast.push(`Welcome back${email ? '' : ''}!`)
      navigate('/app/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <aside className="auth-side">
        <Mesh />
        <div className="content">
          <Link to="/" className="brand">
            <span className="mark"><IconTrend size={18} /></span>
            <span className="word">InferSight</span>
          </Link>
        </div>
        <div className="content tagline">
          <h2>
            Analytics that <em>explain</em> themselves.
          </h2>
          <p>
            KPIs, anomaly alerts, forecasts, and written narratives generated from
            your time-series data — automatically.
          </p>
        </div>
        <div className="content stats">
          <div className="stat">
            <b className="num">4.2σ</b>
            <span>anomaly sensitivity</span>
          </div>
          <div className="stat">
            <b className="num">30d</b>
            <span>forecast horizon</span>
          </div>
          <div className="stat">
            <b className="num">24/7</b>
            <span>monitoring</span>
          </div>
        </div>
      </aside>

      <div className="auth-main">
        <div className="auth-card">
          <h1 className="auth-title">Sign in</h1>
          <p className="auth-sub">Analyze, predict, and act on your data.</p>
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                className="input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                placeholder="you@company.com"
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <div className="input-suffix">
                <input
                  id="password"
                  className="input"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  className="suffix-btn"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  onClick={() => setShowPassword((v) => !v)}
                >
                  {showPassword ? <IconEyeOff size={16} /> : <IconEye size={16} />}
                </button>
              </div>
            </div>
            {error && <div className="field-error">{error}</div>}
            <button className="btn btn-primary btn-lg" type="submit" disabled={busy} style={{ width: '100%' }}>
              {busy ? <span className="spinner" /> : 'Sign in'}
            </button>
          </form>
          <div className="auth-note">
            <IconCheck size={14} />
            Demo account is pre-filled. Or <Link to="/register">create an account</Link>.
          </div>
          <p className="auth-foot">
            New to InferSight? <Link to="/register">Start free</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
