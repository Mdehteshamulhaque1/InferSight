import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../../../api'
import type {
  AlertChannelValue,
  AlertDeliveryOut,
  AlertRuleOut,
  SeverityLevel,
} from '../../../types'
import { useAsync } from '../../../hooks/useAsync'
import { useToast } from '../../ui/Toast'
import { Modal } from '../../ui/Modal'
import { IconBell, IconChevronRight, IconPlus, IconTrash } from '../../ui/icons'
import { fmtDateTime } from '../../../lib/format'

const CHANNELS: { value: AlertChannelValue; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'slack', label: 'Slack' },
  { value: 'webhook', label: 'Webhook' },
]

interface RuleForm {
  severity_threshold: SeverityLevel
  channels: AlertChannelValue[]
  cooldown_minutes: number
  is_active: boolean
}

const EMPTY_FORM: RuleForm = {
  severity_threshold: 'warning',
  channels: ['email'],
  cooldown_minutes: 30,
  is_active: true,
}

interface DeliveryLog {
  items: AlertDeliveryOut[]
  loading: boolean
  error: string | null
}

const SEVERITY_PILL: Record<SeverityLevel, string> = {
  warning: 'pill-amber',
  critical: 'pill-ruby',
}

const STATUS_PILL: Record<string, string> = {
  pending: 'pill-soft',
  sent: 'pill-green',
  failed: 'pill-ruby',
}

export function AlertRulesPanel({ datasetId }: { datasetId: number }) {
  const toast = useToast()
  const rules = useAsync(() => api.listAlertRules(datasetId), [datasetId])

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<AlertRuleOut | null>(null)
  const [form, setForm] = useState<RuleForm>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [channelError, setChannelError] = useState<string | null>(null)

  const [expanded, setExpanded] = useState<number | null>(null)
  const [logs, setLogs] = useState<Record<number, DeliveryLog>>({})

  const list = rules.data?.items ?? []

  function toggleChannel(c: AlertChannelValue) {
    setChannelError(null)
    setForm((f) => ({
      ...f,
      channels: f.channels.includes(c)
        ? f.channels.filter((x) => x !== c)
        : [...f.channels, c],
    }))
  }

  function openCreate() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setSaveError(null)
    setChannelError(null)
    setShowForm(true)
  }

  function openEdit(rule: AlertRuleOut) {
    setEditing(rule)
    setForm({
      severity_threshold: rule.severity_threshold,
      channels: rule.channels,
      cooldown_minutes: rule.cooldown_minutes,
      is_active: rule.is_active,
    })
    setSaveError(null)
    setChannelError(null)
    setShowForm(true)
  }

  function closeForm() {
    setShowForm(false)
    setEditing(null)
    setSaveError(null)
    setChannelError(null)
  }

  async function onSave(e: FormEvent) {
    e.preventDefault()
    if (form.channels.length === 0) {
      setChannelError('Select at least one channel.')
      return
    }
    setSaving(true)
    setSaveError(null)
    try {
      if (editing) {
        await api.updateAlertRule(editing.id, {
          severity_threshold: form.severity_threshold,
          channels: form.channels,
          cooldown_minutes: form.cooldown_minutes,
          is_active: form.is_active,
        })
        toast.push('Alert rule updated')
      } else {
        await api.createAlertRule({
          dataset_id: datasetId,
          severity_threshold: form.severity_threshold,
          channels: form.channels,
          cooldown_minutes: form.cooldown_minutes,
          is_active: form.is_active,
        })
        toast.push('Alert rule created')
      }
      closeForm()
      void rules.refetch()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function onToggleActive(rule: AlertRuleOut) {
    try {
      await api.updateAlertRule(rule.id, { is_active: !rule.is_active })
      void rules.refetch()
    } catch (err) {
      toast.push(err instanceof Error ? err.message : 'Update failed', 'err')
    }
  }

  async function onDelete(rule: AlertRuleOut) {
    if (!window.confirm(`Delete this ${rule.severity_threshold} alert rule? Its delivery history will also be removed.`)) return
    try {
      await api.deleteAlertRule(rule.id)
      toast.push('Alert rule deleted')
      void rules.refetch()
    } catch (err) {
      toast.push(err instanceof Error ? err.message : 'Delete failed', 'err')
    }
  }

  async function loadDeliveryLog(rule: AlertRuleOut) {
    setLogs((m) => ({ ...m, [rule.id]: { items: [], loading: true, error: null } }))
    try {
      const alerts = await api.listAlerts(false, 100)
      const own = (alerts.items ?? []).filter((a) => a.dataset_id === datasetId)
      const collected: AlertDeliveryOut[] = []
      for (const a of own.slice(0, 10)) {
        const res = await api.listAlertDeliveries(a.id)
        collected.push(...(res.items ?? []))
      }
      const items = collected
        .filter((d) => d.rule_id === rule.id)
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
      setLogs((m) => ({ ...m, [rule.id]: { items, loading: false, error: null } }))
    } catch (err) {
      setLogs((m) => ({
        ...m,
        [rule.id]: {
          items: [],
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load delivery history',
        },
      }))
    }
  }

  function toggleLog(rule: AlertRuleOut) {
    const open = expanded === rule.id
    setExpanded(open ? null : rule.id)
    if (!open && !logs[rule.id]) void loadDeliveryLog(rule)
  }

  return (
    <div className="card">
      <div className="section-title">
        <span><IconBell size={15} /> Alert rules</span>
        <button className="btn btn-primary btn-sm" onClick={openCreate}>
          <IconPlus size={14} /> Add rule
        </button>
      </div>

      {rules.loading ? (
        <div className="empty"><span className="spinner" /></div>
      ) : list.length === 0 ? (
        <div className="empty">
          No alert rules for this dataset yet. Add one to route anomaly notifications to email,
          Slack, or a webhook.
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {list.map((rule) => {
            const log = logs[rule.id]
            return (
              <div
                key={rule.id}
                className="card-flat"
                style={{
                  border: '1px solid var(--hairline)',
                  borderRadius: 'var(--r-lg)',
                  padding: '10px 14px',
                  display: 'grid',
                  gap: 8,
                }}
              >
                <div
                  className="row"
                  style={{ justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}
                >
                  <div className="row" style={{ gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span className={`pill ${SEVERITY_PILL[rule.severity_threshold]}`}>
                      {rule.severity_threshold}
                    </span>
                    <span className="row" style={{ gap: 6 }}>
                      {rule.channels.map((c) => (
                        <span key={c} className="pill pill-soft">{c}</span>
                      ))}
                    </span>
                    <span className="num muted" style={{ fontSize: 12 }}>
                      {rule.cooldown_minutes} min cooldown
                    </span>
                    {!rule.is_active && <span className="pill pill-ink">paused</span>}
                  </div>

                  <div className="row" style={{ gap: 6, alignItems: 'center' }}>
                    <label
                      className="switch"
                      title={rule.is_active ? 'Rule active' : 'Rule paused'}
                    >
                      <input
                        type="checkbox"
                        checked={rule.is_active}
                        onChange={() => void onToggleActive(rule)}
                        aria-label={rule.is_active ? 'Pause rule' : 'Activate rule'}
                      />
                      <span className="track" />
                    </label>
                    <button className="btn btn-ghost btn-sm" onClick={() => openEdit(rule)}>
                      Edit
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ color: 'var(--ruby)' }}
                      title="Delete rule"
                      aria-label="Delete rule"
                      onClick={() => void onDelete(rule)}
                    >
                      <IconTrash size={14} />
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => toggleLog(rule)}>
                      <span
                        style={{
                          display: 'inline-flex',
                          transform: expanded === rule.id ? 'rotate(90deg)' : undefined,
                          transition: 'transform var(--dur) var(--ease)',
                        }}
                      >
                        <IconChevronRight size={13} />
                      </span>
                      Delivery log
                    </button>
                  </div>
                </div>

                {expanded === rule.id && (
                  <div className="table-scroll">
                    {log?.loading ? (
                      <div className="empty" style={{ padding: '12px 0' }}>
                        <span className="spinner" />
                      </div>
                    ) : log?.error ? (
                      <div className="field-error">{log.error}</div>
                    ) : !log || log.items.length === 0 ? (
                      <div className="empty" style={{ padding: '12px 0', fontSize: 13 }}>
                        No deliveries recorded for this rule yet.
                      </div>
                    ) : (
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Channel</th>
                            <th>Status</th>
                            <th>Sent</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {log.items.slice(0, 12).map((d) => (
                            <tr key={d.id}>
                              <td className="strong">{d.channel}</td>
                              <td>
                                <span
                                  className={`pill ${STATUS_PILL[d.status] ?? 'pill-soft'}`}
                                  title={d.error_message ?? undefined}
                                >
                                  {d.status}
                                </span>
                              </td>
                              <td className="num">{fmtDateTime(d.sent_at)}</td>
                              <td>
                                {d.status === 'failed' && d.error_message && (
                                  <span className="field-error" style={{ fontSize: 12 }}>
                                    {d.error_message}
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <Modal
        title={editing ? 'Edit alert rule' : 'Add alert rule'}
        subtitle={
          editing
            ? 'Update how anomalies on this dataset trigger notifications.'
            : 'Pick a severity threshold and the channels that should be notified.'
        }
        open={showForm}
        onClose={closeForm}
        footer={
          <>
            <button className="btn btn-secondary" onClick={closeForm}>Cancel</button>
            <button
              className="btn btn-primary"
              type="submit"
              form="alert-rule-form"
              disabled={saving}
            >
              {saving ? <span className="spinner" /> : editing ? 'Save changes' : 'Add rule'}
            </button>
          </>
        }
      >
        <form id="alert-rule-form" onSubmit={onSave} className="form-grid">
          <div className="field">
            <label htmlFor="rule-severity">Severity threshold</label>
            <select
              id="rule-severity"
              className="select"
              value={form.severity_threshold}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  severity_threshold: e.target.value as SeverityLevel,
                }))
              }
            >
              <option value="warning">warning</option>
              <option value="critical">critical</option>
            </select>
          </div>

          <div className="field">
            <label htmlFor="rule-cooldown">Cooldown (minutes)</label>
            <input
              id="rule-cooldown"
              className="input"
              type="number"
              min={1}
              max={10080}
              value={form.cooldown_minutes}
              onChange={(e) =>
                setForm((f) => ({ ...f, cooldown_minutes: Number(e.target.value) }))
              }
            />
          </div>

          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label>Channels</label>
            <div className="row" style={{ gap: 18, flexWrap: 'wrap' }}>
              {CHANNELS.map((c) => (
                <label key={c.value} className="check" style={{ marginBottom: 0 }}>
                  <input
                    type="checkbox"
                    checked={form.channels.includes(c.value)}
                    onChange={() => toggleChannel(c.value)}
                  />
                  <span className="box" />
                  <span>{c.label}</span>
                </label>
              ))}
            </div>
            {channelError && <div className="field-error mt-2">{channelError}</div>}
          </div>

          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <div className="row" style={{ gap: 10 }}>
              <span style={{ flex: 1 }}>Active</span>
              <label className="switch" style={{ marginBottom: 0 }}>
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                  aria-label="Rule active"
                />
                <span className="track" />
              </label>
            </div>
          </div>

          {saveError && (
            <div className="field-error" style={{ gridColumn: '1 / -1' }}>{saveError}</div>
          )}
        </form>
      </Modal>
    </div>
  )
}
