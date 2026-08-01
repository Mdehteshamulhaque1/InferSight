import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../../api'
import type { RelatedSignalOut } from '../../../types'

interface RelatedSignalsPanelProps {
  datasetId: number
  anomalyId: number
}

interface LoadState {
  loading: boolean
  items: RelatedSignalOut[] | null
  error: string | null
}

function DirectionIcon({ direction }: { direction: string }) {
  const same = direction === 'same'
  return (
    <svg
      width={15}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ color: 'var(--ink-mute)' }}
      role="img"
      aria-label={same ? 'moved together' : 'moved opposite'}
    >
      <title>{same ? 'moved together' : 'moved opposite'}</title>
      <path d="M0 13l3.5-5 3.5 5" />
      {same ? (
        <path d="M8 13l3.5-5 3.5 5" />
      ) : (
        <path d="M8 10.5l3.5 5 3.5-5" />
      )}
    </svg>
  )
}

export function RelatedSignalsPanel({ datasetId, anomalyId }: RelatedSignalsPanelProps) {
  const [state, setState] = useState<LoadState>({ loading: true, items: null, error: null })

  useEffect(() => {
    let alive = true
    setState({ loading: true, items: null, error: null })
    api
      .getRelatedSignals(datasetId, anomalyId)
      .then((items) => {
        if (alive) setState({ loading: false, items, error: null })
      })
      .catch((e) => {
        if (alive) {
          setState({
            loading: false,
            items: null,
            error: e instanceof Error ? e.message : 'Failed to load related signals',
          })
        }
      })
    return () => {
      alive = false
    }
  }, [datasetId, anomalyId])

  if (state.loading) {
    return (
      <div className="row" style={{ gap: 8, alignItems: 'center', color: 'var(--ink-mute)', fontSize: 12 }}>
        <span className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
        Checking related datasets…
      </div>
    )
  }

  if (state.error) {
    return <div className="field-error">{state.error}</div>
  }

  if (!state.items || state.items.length === 0) {
    return <div className="muted" style={{ fontSize: 12 }}>No related signals detected</div>
  }

  return (
    <div style={{ display: 'grid', gap: 4 }}>
      {state.items.map((s) => (
        <Link key={s.dataset_id} to={`/app/datasets/${s.dataset_id}`} className="rel-signal">
          <span
            className="strong"
            style={{ fontSize: 13, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          >
            {s.dataset_name}
          </span>
          <span className="row" style={{ gap: 8, alignItems: 'center', flex: 'none' }}>
            <span
              style={{
                width: 44,
                height: 4,
                borderRadius: 2,
                background: 'var(--hairline-strong)',
                overflow: 'hidden',
                display: 'inline-block',
              }}
            >
              <span
                style={{
                  display: 'block',
                  height: '100%',
                  width: `${Math.min(100, Math.max(4, Math.round(Math.abs(s.correlation) * 100)))}%`,
                  background: 'var(--ink-mute)',
                }}
              />
            </span>
            <span className="num" style={{ fontSize: 12, color: 'var(--ink-mute)', width: 34, textAlign: 'right' }}>
              {s.correlation.toFixed(2)}
            </span>
            <DirectionIcon direction={s.direction} />
          </span>
        </Link>
      ))}
    </div>
  )
}
