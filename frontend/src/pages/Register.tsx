import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../app/providers/AuthContext'
import { Mesh } from '../components/ui/Mesh'
import { useToast } from '../components/ui/Toast'
import { usePageTitle } from '../hooks/usePageTitle'
import { IconEye, IconEyeOff, IconTrend } from '../components/ui/icons'

export function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  usePageTitle('Create account')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register(email, password, fullName)
      toast.push(`Welcome to InferSight, ${fullName.split(' ')[0] || 'friend'}!`)
      navigate('/app/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
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
            Your data, <em>narrated.</em>
          </h2>
          <p>
            Ingest a time series once. InferSight resamples, trends, and scores it
            automatically — then writes the analysis for you.
          </p>
        </div>
        <div className="content stats">
          <div className="stat">
            <b className="num">75+</b>
            <span>API tests green</span>
          </div>
          <div className="stat">
            <b className="num">0</b>
            <span>credit card required</span>
          </div>
          <div className="stat">
            <b className="num">1</b>
            <span>minute to first insight</span>
          </div>
        </div>
      </aside>

      <div className="auth-main">
        <div className="auth-card">
          <h1 className="auth-title">Create your account</h1>
          <p className="auth-sub">Free during the alpha. Your data stays yours.</p>
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="full_name">Full name</label>
              <input
                id="full_name"
                className="input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
                placeholder="Ada Lovelace"
                required
              />
            </div>
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
                required
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
                  autoComplete="new-password"
                  placeholder="••••••••"
                  required
                  minLength={8}
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
              <div className="hint">8+ characters with at least one letter and one digit.</div>
            </div>
            {error && <div className="field-error">{error}</div>}
            <button className="btn btn-primary btn-lg" type="submit" disabled={busy} style={{ width: '100%' }}>
              {busy ? <span className="spinner" /> : 'Create account'}
            </button>
          </form>
          <p className="auth-foot">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
