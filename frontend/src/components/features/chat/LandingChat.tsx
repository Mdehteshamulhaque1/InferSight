import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../../api'
import { useAuth } from '../../../app/providers/AuthContext'
import { IconArrowRight, IconChat, IconClose } from '../../ui/icons'

interface Msg {
  role: 'user' | 'assistant'
  text: string
  error?: boolean
  followups?: string[]
}

function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.message
  return 'Something went wrong sending your message. Please try again.'
}

export function LandingChat() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading, open])

  async function send(text?: string) {
    const message = (text ?? input).trim()
    if (!message || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text: message }])
    setLoading(true)
    try {
      const out = await api.chat(message)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: out.reply, followups: out.followups },
      ])
    } catch (e) {
      setMessages((prev) => [...prev, { role: 'assistant', text: errorText(e), error: true }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {open && (
        <section className="chat-panel" aria-label="InferSight assistant">
          <header className="chat-head">
            <span className="dot" aria-hidden="true" />
            <span className="name">InferSight assistant</span>
            <button
              type="button"
              className="close"
              aria-label="Close chat"
              onClick={() => setOpen(false)}
            >
              <IconClose size={16} />
            </button>
          </header>
          <div className="chat-body" ref={bodyRef}>
            {user ? (
              messages.length === 0 && !loading ? (
                <div className="chat-guest">
                  <p>
                    Ask about your data in plain language — trends, anomalies, forecasts, health,
                    or what to do next.
                  </p>
                </div>
              ) : (
                messages.map((m, i) => (
                  <div key={i}>
                    <div className={`msg ${m.role}${m.error ? ' error' : ''}`}>{m.text}</div>
                    {m.followups && m.followups.length > 0 && !m.error && (
                      <div className="chat-followups">
                        {m.followups.map((f) => (
                          <button key={f} type="button" onClick={() => void send(f)}>
                            {f}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )
            ) : (
              <div className="chat-guest">
                <p>Sign in to chat with your data — the assistant analyzes your own datasets.</p>
                <Link to="/login">Sign in to chat</Link>
              </div>
            )}
            {loading && (
              <div className="msg assistant">
                <span className="typing" aria-label="Thinking">
                  <i />
                  <i />
                  <i />
                </span>
              </div>
            )}
          </div>
          {user && (
            <form
              className="chat-input-row"
              onSubmit={(e) => {
                e.preventDefault()
                void send()
              }}
            >
              <input
                className="chat-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your data…"
                aria-label="Message"
                disabled={loading}
              />
              <button type="submit" className="chat-send" disabled={loading || !input.trim()} aria-label="Send">
                <IconArrowRight size={16} />
              </button>
            </form>
          )}
        </section>
      )}
      <button
        type="button"
        className="chat-fab"
        aria-label={open ? 'Close chat' : 'Open chat'}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <IconClose size={20} /> : <IconChat size={22} />}
      </button>
    </>
  )
}
