import { useEffect, useState } from 'react'
import type { JSX } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../app/providers/AuthContext'
import { api } from '../../api'
import { useAsync } from '../../hooks/useAsync'
import { CommandPalette } from './CommandPalette'
import type { IconProps } from '../ui/icons'
import {
  IconBell,
  IconChat,
  IconDashboard,
  IconDataset,
  IconDownload,
  IconInsight,
  IconLogout,
  IconMenu,
  IconSearch,
  IconTrend,
  IconUpload,
} from '../ui/icons'

interface NavItem {
  to: string
  label: string
  icon: (p: IconProps) => JSX.Element
  badge?: boolean
}

const sections: { label: string; items: NavItem[] }[] = [
  {
    label: 'Workspace',
    items: [
      { to: '/app/home', label: 'Copilot', icon: IconChat },
      { to: '/app/dashboard', label: 'Dashboard', icon: IconDashboard },
      { to: '/app/upload', label: 'Upload', icon: IconUpload },
      { to: '/app/insights', label: 'Insights', icon: IconInsight },
    ],
  },
  {
    label: 'Monitor',
    items: [{ to: '/app/alerts', label: 'Alerts', icon: IconBell, badge: true }],
  },
  {
    label: 'Data',
    items: [{ to: '/app/datasets', label: 'Datasets', icon: IconDataset }],
  },
  {
    label: 'Output',
    items: [{ to: '/app/reports', label: 'Reports', icon: IconDownload }],
  },
]

const titles: Record<string, string> = {
  '/app/home': 'Copilot',
  '/app/dashboard': 'Dashboard',
  '/app/upload': 'Upload',
  '/app/datasets': 'Datasets',
  '/app/alerts': 'Alerts',
  '/app/insights': 'Insights',
  '/app/reports': 'Reports',
}

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const unread = useAsync(() => api.unreadAlerts(), [])

  const unreadCount = unread.data?.count ?? 0
  const current =
    titles[location.pathname] ?? (location.pathname.startsWith('/app/datasets/') ? 'Dataset' : '')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="shell">
      <div
        className={`sidebar-scrim${sidebarOpen ? ' show' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />
      <aside className={`sidebar${sidebarOpen ? ' open' : ''}`}>
        <Link className="side-brand" to="/" title="Go to InferSight home">
          <span className="mark">
            <IconTrend size={16} />
          </span>
          <span className="word">InferSight</span>
        </Link>
        <nav className="side-nav" aria-label="Main">
          {sections.map((s) => (
            <div key={s.label}>
              <div className="nav-section-label">{s.label}</div>
              {s.items.map(({ to, label, icon: Icon, badge }) => (
                <NavLink
                  key={to}
                  to={to}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                >
                  <Icon className="ico" />
                  <span>{label}</span>
                  {badge && unreadCount > 0 && (
                    <span className="nav-badge pulse num">{unreadCount > 99 ? '99+' : unreadCount}</span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="side-foot">
          <div className="side-user">
            <div className="avatar">{user?.full_name?.charAt(0)?.toUpperCase() ?? '?'}</div>
            <div className="meta">
              <div className="name">{user?.full_name ?? '…'}</div>
              <div className="role">{user?.role ?? 'member'}</div>
            </div>
            <button
              className="icon-btn"
              title="Sign out"
              aria-label="Sign out"
              onClick={() => void logout()}
              style={{
                background: 'transparent',
                borderColor: 'var(--hairline-strong)',
                color: 'var(--ink-secondary)',
              }}
            >
              <IconLogout size={16} />
            </button>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="row" style={{ gap: 12, minWidth: 0 }}>
            <button
              className="menu-trigger"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <IconMenu size={18} />
            </button>
            <div className="crumb">
              <a href="/app/dashboard">InferSight</a>
              {current && (
                <>
                  <span className="sep">/</span>
                  <span className="current">{current}</span>
                </>
              )}
            </div>
          </div>
          <div className="actions">
            <button
              className="kbd-hint"
              onClick={() => setPaletteOpen(true)}
              aria-label="Open command palette"
            >
              <IconSearch size={15} />
              <span className="text">Search</span>
              <kbd>⌘K</kbd>
            </button>
            <button
              className="icon-btn"
              aria-label="Alerts"
              onClick={() => navigate('/app/alerts')}
            >
              <IconBell size={16} />
              {unreadCount > 0 && (
                <span className="dot-badge num">{unreadCount > 99 ? '99+' : unreadCount}</span>
              )}
            </button>
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
