import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import type { DatasetRead } from '../types'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import { useToast } from '../components/ui/Toast'
import { Modal } from '../components/ui/Modal'
import {
  IconArrowRight,
  IconCheck,
  IconDataset,
  IconPlus,
  IconSearch,
  IconTrash,
} from '../components/ui/icons'
import { fmtDate } from '../lib/format'

const GRANULARITIES = ['hour', 'day', 'week', 'month']
const METRIC_TYPES = ['revenue', 'count', 'latency', 'conversion', 'custom']

interface FormState {
  name: string
  slug: string
  description: string
  metric_type: string
  unit: string
  currency: string
  granularity: string
}

const EMPTY_FORM: FormState = {
  name: '',
  slug: '',
  description: '',
  metric_type: 'revenue',
  unit: '',
  currency: 'USD',
  granularity: 'day',
}

const SAMPLE_POINTS = `2026-01-01T00:00:00Z,1000
2026-01-02T00:00:00Z,1180
2026-01-03T00:00:00Z,1225
2026-01-04T00:00:00Z,1140
2026-01-05T00:00:00Z,1330
2026-01-06T00:00:00Z,1385
2026-01-07T00:00:00Z,1295
2026-01-08T00:00:00Z,1520
2026-01-09T00:00:00Z,1610
2026-01-10T00:00:00Z,1545`

export function Datasets() {
  const toast = useToast()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  usePageTitle('Datasets')
  const datasets = useAsync(() => api.listDatasets(1, 100), [])
  const [query, setQuery] = useState('')

  const [showCreate, setShowCreate] = useState(searchParams.get('new') === '1')
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [createError, setCreateError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const [ingestFor, setIngestFor] = useState<DatasetRead | null>(null)
  const [pointsText, setPointsText] = useState(SAMPLE_POINTS)
  const [ingestError, setIngestError] = useState<string | null>(null)
  const [ingesting, setIngesting] = useState(false)

  const list = datasets.data?.items ?? []

  useEffect(() => {
    if (searchParams.get('new') === '1') {
      setShowCreate(true)
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return list
    return list.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        d.slug.toLowerCase().includes(q) ||
        d.metric_type.toLowerCase().includes(q)
    )
  }, [list, query])

  function set<K extends keyof FormState>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    setCreating(true)
    setCreateError(null)
    try {
      await api.createDataset({
        name: form.name,
        slug: form.slug || undefined,
        description: form.description || undefined,
        metric_type: form.metric_type,
        unit: form.unit || undefined,
        currency: form.currency || undefined,
        granularity: form.granularity,
      })
      toast.push('Dataset created')
      setForm(EMPTY_FORM)
      setShowCreate(false)
      void datasets.refetch()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  async function onIngest(e: FormEvent) {
    e.preventDefault()
    if (!ingestFor) return
    setIngesting(true)
    setIngestError(null)
    try {
      const points = pointsText
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.length > 0)
        .map((line) => {
          const [timestamp, value] = line.split(',')
          if (!timestamp || value == null) throw new Error(`Malformed line: "${line}"`)
          const num = Number(value)
          if (!Number.isFinite(num)) throw new Error(`Invalid value in line: "${line}"`)
          return { timestamp: timestamp.trim(), value: num }
        })
      if (points.length === 0) throw new Error('No points to ingest')
      const res = await api.ingestPoints(ingestFor.id, points)
      toast.push(
        `Ingested ${res.inserted} point${res.inserted === 1 ? '' : 's'}` +
          (res.skipped_duplicates > 0 ? ` · ${res.skipped_duplicates} duplicates skipped` : '')
      )
      setIngestFor(null)
      void datasets.refetch()
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : 'Ingest failed')
    } finally {
      setIngesting(false)
    }
  }

  async function onDelete(d: DatasetRead) {
    if (!window.confirm(`Delete dataset "${d.name}" and all of its points?`)) return
    try {
      await api.deleteDataset(d.id)
      toast.push('Dataset deleted')
      void datasets.refetch()
    } catch (err) {
      toast.push(err instanceof Error ? err.message : 'Delete failed', 'err')
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Datasets</h1>
          <p className="sub">Ingest time-series metrics and manage your data sources.</p>
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            <IconPlus size={15} /> New dataset
          </button>
        </div>
      </div>

      <div className="toolbar">
        <div className="search">
          <IconSearch size={15} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search datasets…"
            aria-label="Search datasets"
          />
          {query && (
            <button className="search-clear" aria-label="Clear search" onClick={() => setQuery('')}>
              ×
            </button>
          )}
        </div>
        <span className="num muted" style={{ fontSize: 12 }}>
          {filtered.length} of {list.length}
        </span>
      </div>

      <div className="table-wrap table-scroll">
        {datasets.loading ? (
          <div className="empty"><span className="spinner" /></div>
        ) : list.length === 0 ? (
          <div className="empty">
            <span className="empty-state">
              <span className="ico"><IconDataset size={20} /></span>
              <h3>No datasets yet</h3>
              <p>Create your first dataset to begin ingesting time-series data.</p>
              <button className="btn btn-primary mt-4" onClick={() => setShowCreate(true)}>
                <IconPlus size={15} /> New dataset
              </button>
            </span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty">No datasets match “{query}”.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Type</th>
                <th>Granularity</th>
                <th className="num">Points</th>
                <th>Last point</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d) => (
                <tr key={d.id} onClick={() => navigate(`/app/datasets/${d.id}`)}>
                  <td>
                    <div className="strong">{d.name}</div>
                    <div className="muted mono" style={{ fontSize: 12 }}>/{d.slug}</div>
                  </td>
                  <td><span className="pill pill-soft">{d.metric_type}</span></td>
                  <td className="num">{d.granularity}</td>
                  <td className="num">{d.point_count.toLocaleString()}</td>
                  <td className="num">{fmtDate(d.last_point_at)}</td>
                  <td className="num">{fmtDate(d.created_at)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <div className="row" style={{ gap: 4, justifyContent: 'flex-end' }}>
                      <button
                        className="btn btn-ghost btn-sm"
                        title="Quick paste import"
                        aria-label="Quick import"
                        onClick={(e) => {
                          e.stopPropagation()
                          setIngestFor(d)
                        }}
                      >
                        <IconPlus size={14} />
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        title="Open dataset"
                        aria-label="Open"
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/app/datasets/${d.id}`)
                        }}
                      >
                        <IconArrowRight size={14} />
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ color: 'var(--ruby)' }}
                        title="Delete dataset"
                        aria-label="Delete"
                        onClick={(e) => {
                          e.stopPropagation()
                          void onDelete(d)
                        }}
                      >
                        <IconTrash size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create dataset modal */}
      <Modal
        title="Create dataset"
        subtitle="Define a new time-series source. You can import data right after."
        open={showCreate}
        onClose={() => setShowCreate(false)}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setShowCreate(false)}>
              Cancel
            </button>
            <button className="btn btn-primary" type="submit" form="create-dataset-form" disabled={creating}>
              {creating ? <span className="spinner" /> : 'Create dataset'}
            </button>
          </>
        }
      >
        <form id="create-dataset-form" onSubmit={onCreate} className="form-grid">
          <div className="field">
            <label htmlFor="ds-name">Name</label>
            <input
              id="ds-name"
              className="input"
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
              placeholder="Monthly revenue"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="ds-slug">Slug</label>
            <input
              id="ds-slug"
              className="input"
              value={form.slug}
              onChange={(e) => set('slug', e.target.value)}
              placeholder="monthly-revenue (auto if blank)"
            />
          </div>
          <div className="field">
            <label htmlFor="ds-metric">Metric type</label>
            <select
              id="ds-metric"
              className="select"
              value={form.metric_type}
              onChange={(e) => set('metric_type', e.target.value)}
            >
              {METRIC_TYPES.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="ds-granularity">Granularity</label>
            <select
              id="ds-granularity"
              className="select"
              value={form.granularity}
              onChange={(e) => set('granularity', e.target.value)}
            >
              {GRANULARITIES.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="ds-currency">Currency</label>
            <input
              id="ds-currency"
              className="input"
              value={form.currency}
              onChange={(e) => set('currency', e.target.value)}
              placeholder="USD"
            />
          </div>
          <div className="field">
            <label htmlFor="ds-unit">Unit</label>
            <input
              id="ds-unit"
              className="input"
              value={form.unit}
              onChange={(e) => set('unit', e.target.value)}
              placeholder="requests"
            />
          </div>
          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label htmlFor="ds-description">Description</label>
            <input
              id="ds-description"
              className="input"
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              placeholder="What does this metric capture?"
            />
          </div>
          {createError && <div className="field-error" style={{ gridColumn: '1 / -1' }}>{createError}</div>}
        </form>
      </Modal>

      {/* Quick ingest modal */}
      <Modal
        title={`Ingest points`}
        subtitle={
          ingestFor
            ? `Adding data to ${ingestFor.name} — CSV lines of timestamp,value. Ingestion is idempotent; duplicate timestamps are skipped.`
            : ''
        }
        open={ingestFor != null}
        onClose={() => setIngestFor(null)}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setIngestFor(null)}>
              Cancel
            </button>
            <button className="btn btn-primary" type="submit" form="ingest-points-form" disabled={ingesting}>
              {ingesting ? <span className="spinner" /> : 'Ingest'}
            </button>
          </>
        }
      >
        <form id="ingest-points-form" onSubmit={onIngest}>
          <div className="field">
            <label htmlFor="ingest-textarea">Points (timestamp,value per line)</label>
            <textarea
              id="ingest-textarea"
              className="textarea"
              value={pointsText}
              onChange={(e) => setPointsText(e.target.value)}
              spellCheck={false}
            />
          </div>
          {ingestError && <div className="field-error">{ingestError}</div>}
          <div className="row" style={{ gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            <span className="pill pill-green"><IconCheck size={11} /> idempotent</span>
            <span className="pill pill-soft">duplicates skipped</span>
          </div>
        </form>
      </Modal>
    </div>
  )
}
