import { api } from '../api'
import type { AlertOut } from '../types'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import { useToast } from '../components/ui/Toast'
import { IconBell, IconCheck, IconCheckCircle } from '../components/ui/icons'
import { fmtDateTime, severityClass } from '../lib/format'

export function Alerts() {
  const toast = useToast()
  usePageTitle('Alerts')
  const alerts = useAsync(() => api.listAlerts(false, 100), [])
  const unread = useAsync(() => api.unreadAlerts(), [])

  const items = alerts.data?.items ?? []
  const unreadCount = unread.data?.count ?? 0
  const hasUnread = items.some((a) => !a.is_read)

  async function onMarkRead(a: AlertOut) {
    try {
      await api.markAlertRead(a.id)
      void alerts.refetch()
      void unread.refetch()
    } catch (e) {
      toast.push(e instanceof Error ? e.message : 'Failed to update', 'err')
    }
  }

  async function onMarkAll() {
    try {
      const res = await api.markAllAlertsRead()
      toast.push(res.detail)
      void alerts.refetch()
      void unread.refetch()
    } catch (e) {
      toast.push(e instanceof Error ? e.message : 'Failed to update', 'err')
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <p className="sub">Monitoring events raised by the anomaly engine.</p>
        </div>
        <div className="actions">
          <span className={`pill ${unreadCount > 0 ? 'pill-ruby' : 'pill-green'}`}>
            {unreadCount > 0 ? (
              <>{unreadCount} unread</>
            ) : (
              <>
                <IconCheckCircle size={12} /> All caught up
              </>
            )}
          </span>
          {hasUnread && (
            <button className="btn btn-secondary" onClick={() => void onMarkAll()}>
              <IconCheck size={14} /> Mark all read
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <div className="section-title">
          <span><IconBell size={15} /> Alert feed</span>
          <span className="num muted">{items.length} total</span>
        </div>
        {alerts.loading ? (
          <div className="empty"><span className="spinner" /></div>
        ) : items.length === 0 ? (
          <div className="empty">
            <span className="empty-state">
              <span className="ico"><IconBell size={20} /></span>
              <h3>No alerts yet</h3>
              <p>Open a dataset and run the anomaly detector to populate this feed.</p>
            </span>
          </div>
        ) : (
          <div style={{ maxHeight: 640, overflowY: 'auto' }}>
            {items.map((a) => (
              <div key={a.id} className={`insight${a.is_read ? ' dim' : ''}`}>
                <div className={`dot ${severityClass(a.severity)}`} />
                <div className="body">
                  <div className="row" style={{ gap: 8, justifyContent: 'space-between', flexWrap: 'wrap' }}>
                    <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                      <span className={`pill ${a.severity === 'critical' ? 'pill-primary' : a.severity === 'warning' ? 'pill-ink' : 'pill-soft'}`}>
                        {a.severity}
                      </span>
                      <span className="pill pill-soft">{a.kind}</span>
                      {!a.is_read && <span className="pill pill-primary">new</span>}
                    </div>
                    <span className="muted num" style={{ fontSize: 12 }}>
                      {fmtDateTime(a.created_at)}
                    </span>
                  </div>
                  <div className="title" style={{ marginTop: 8 }}>{a.title}</div>
                  <div className="text">{a.body}</div>
                  {!a.is_read && (
                    <button className="btn btn-ghost btn-sm mt-2" onClick={() => void onMarkRead(a)}>
                      Mark read
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
