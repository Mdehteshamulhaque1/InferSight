import { useEffect, useMemo, useRef, useState } from 'react'
import type { JSX } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../app/providers/AuthContext'
import { api } from '../../api'
import { useAsync } from '../../hooks/useAsync'
import type { IconProps } from '../ui/icons'
import {
  IconBell,
  IconDashboard,
  IconDataset,
  IconInsight,
  IconLogout,
  IconPlus,
  IconSearch,
} from '../ui/icons'

interface Command {
  label: string
  to: string | null
  icon: (p: IconProps) => JSX.Element
  group: string
  meta: string
  shortcut?: string
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()
  const { logout } = useAuth()
  const [query, setQuery] = useState('')
  const [hl, setHl] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const unread = useAsync(() => api.unreadAlerts(), [])

  useEffect(() => {
    if (open) {
      setQuery('')
      setHl(0)
      const id = window.setTimeout(() => inputRef.current?.focus(), 30)
      return () => window.clearTimeout(id)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const commands: Command[] = useMemo(() => {
    const unreadCount = unread.data?.count ?? 0
    const nav = [
      { label: 'Go to Dashboard', to: '/app/dashboard', icon: IconDashboard, group: 'Navigate', meta: 'Dashboards', shortcut: 'g d' },
      { label: 'Go to Datasets', to: '/app/datasets', icon: IconDataset, group: 'Navigate', meta: 'Data sources', shortcut: 'g s' },
      { label: 'Go to Alerts', to: '/app/alerts', icon: IconBell, group: 'Navigate', meta: unreadCount > 0 ? `${unreadCount} unread` : 'Feed', shortcut: 'g a' },
      { label: 'Go to Insights', to: '/app/insights', icon: IconInsight, group: 'Navigate', meta: 'AI analysis', shortcut: 'g i' },
    ]
    const actions = [
      { label: 'Create a new dataset', to: '/app/datasets?new=1', icon: IconPlus, group: 'Actions', meta: 'New' },
      { label: 'Sign out', to: null, icon: IconLogout, group: 'Actions', meta: 'Session' },
    ]
    return [...nav, ...actions]
  }, [unread.data?.count])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return commands
    return commands.filter((c) =>
      c.label.toLowerCase().includes(q) || c.group.toLowerCase().includes(q)
    )
  }, [commands, query])

  useEffect(() => {
    setHl(0)
  }, [query])

  useEffect(() => {
    if (hl >= filtered.length) setHl(Math.max(0, filtered.length - 1))
  }, [filtered.length, hl])

  function run(cmd: Command) {
    onClose()
    if (cmd.to) {
      navigate(cmd.to)
    } else {
      void logout()
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHl((h) => Math.min(filtered.length - 1, h + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHl((h) => Math.max(0, h - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const cmd = filtered[hl]
      if (cmd) run(cmd)
    }
  }

  if (!open) return null

  const groups: { name: string; items: typeof filtered }[] = []
  for (const c of filtered) {
    const g = groups.find((x) => x.name === c.group)
    if (g) g.items.push(c)
    else groups.push({ name: c.group, items: [c] })
  }

  return (
    <div className="overlay" style={{ alignItems: 'flex-start' }} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Command palette">
        <div className="palette-input">
          <IconSearch size={18} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Type a command or search…"
            aria-label="Search commands"
          />
          <kbd>esc</kbd>
        </div>
        <div className="palette-list">
          {groups.length === 0 && <div className="palette-empty">No commands match “{query}”.</div>}
          {groups.map((g) => (
            <div key={g.name}>
              <div className="palette-group-label">{g.name}</div>
              {g.items.map((c) => {
                const Icon = c.icon
                const idx = filtered.indexOf(c)
                return (
                  <button
                    key={`${c.group}-${c.label}`}
                    className={`palette-item${idx === hl ? ' hl' : ''}`}
                    onMouseEnter={() => setHl(idx)}
                    onClick={() => run(c)}
                  >
                    <span className="ico"><Icon size={16} /></span>
                    <span>{c.label}</span>
                    {c.shortcut && <span className="meta"><kbd>{c.shortcut}</kbd></span>}
                    <span className="meta">{c.meta}</span>
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
