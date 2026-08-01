import { useEffect, useMemo, useRef, useState } from 'react'
import type { Anomaly, ForecastPoint, SeriesPoint } from '../../types'
import { RelatedSignalsPanel } from '../features/related-signals/RelatedSignalsPanel'

interface LineChartProps {
  data: SeriesPoint[]
  trend?: SeriesPoint[]
  forecast?: ForecastPoint[]
  anomalies?: Anomaly[]
  datasetId?: number
  height?: number
  formatY?: (v: number) => string
}

interface Pt {
  ts: string
  v: number
}

const toPts = (d: SeriesPoint[]): Pt[] => d.map((p) => ({ ts: p.timestamp, v: p.value }))
const toFPts = (d: ForecastPoint[]): Pt[] => d.map((p) => ({ ts: p.timestamp, v: p.value }))

const M_FULL = { top: 14, right: 14, bottom: 28, left: 48 }
const M_MIN = { top: 4, right: 4, bottom: 4, left: 4 }

function niceNum(range: number, round: boolean): number {
  const exp = Math.floor(Math.log10(range))
  const frac = range / Math.pow(10, exp)
  let nf
  if (round) {
    if (frac < 1.5) nf = 1
    else if (frac < 3) nf = 2
    else if (frac < 7) nf = 5
    else nf = 10
  } else {
    if (frac <= 1) nf = 1
    else if (frac <= 2) nf = 2
    else if (frac <= 5) nf = 5
    else nf = 10
  }
  return nf * Math.pow(10, exp)
}

function ticks(min: number, max: number, count: number): number[] {
  if (min === max) return [min]
  const range = niceNum(max - min, false)
  const step = niceNum(range / Math.max(1, count - 1), true)
  const niceMin = Math.floor(min / step) * step
  const out: number[] = []
  for (let v = niceMin; v <= max + step * 1e-6; v += step) out.push(Math.round(v * 1e6) / 1e6)
  return out
}

function fmtCompact(n: number): string {
  const abs = Math.abs(n)
  if (abs >= 1e9) return `${(n / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (abs >= 1e4) return `${(n / 1e3).toFixed(1)}k`
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function fmtDate(ts: string, spanDays: number): string {
  const d = new Date(ts)
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: spanDays > 200 ? 'numeric' : undefined,
  })
}

/** Monotone (Catmull-Rom → bezier) path so line segments join smoothly. */
function smoothPath(pts: Pt[], x: (t: string) => number, y: (v: number) => number): string {
  if (pts.length === 0) return ''
  if (pts.length === 1) {
    return `M ${x(pts[0].ts).toFixed(2)} ${y(pts[0].v).toFixed(2)}`
  }
  let d = `M ${x(pts[0].ts).toFixed(2)} ${y(pts[0].v).toFixed(2)}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    const c1x = x(p1.ts) + (x(p2.ts) - x(p0.ts)) / 6
    const c1y = y(p1.v) + (y(p2.v) - y(p0.v)) / 6
    const c2x = x(p2.ts) - (x(p3.ts) - x(p1.ts)) / 6
    const c2y = y(p2.v) - (y(p3.v) - y(p1.v)) / 6
    d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${x(p2.ts).toFixed(2)} ${y(p2.v).toFixed(2)}`
  }
  return d
}

export function LineChart({
  data,
  trend,
  forecast,
  anomalies,
  datasetId,
  height = 300,
  formatY,
}: LineChartProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(720)
  const [hover, setHover] = useState<number | null>(null)
  const [selAnomaly, setSelAnomaly] = useState<{ anomaly: Anomaly; index: number } | null>(null)

  useEffect(() => {
    setSelAnomaly(null)
  }, [datasetId])

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w) setWidth(w)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const minimal = height < 90
  const M = minimal ? M_MIN : M_FULL

  const { x, y, xTicks, yTicks, spanDays, iw, lo } = useMemo(() => {
    const all: Pt[] = [
      ...data.map((p) => ({ ts: p.timestamp, v: p.value })),
      ...(trend ?? []).map((p) => ({ ts: p.timestamp, v: p.value })),
      ...(forecast ?? []).map((p) => ({
        ts: p.timestamp,
        v: Math.max(p.value, p.lower ?? p.value, p.upper ?? p.value),
      })),
      ...(forecast ?? []).map((p) => ({
        ts: p.timestamp,
        v: Math.min(p.value, p.lower ?? p.value, p.upper ?? p.value),
      })),
    ]
    const tMin = all.length ? Math.min(...all.map((p) => new Date(p.ts).getTime())) : 0
    const tMax = all.length ? Math.max(...all.map((p) => new Date(p.ts).getTime())) : 1
    const vMin = all.length ? Math.min(...all.map((p) => p.v)) : 0
    const vMax = all.length ? Math.max(...all.map((p) => p.v)) : 1
    const pad = Math.max((vMax - vMin) * 0.08, Math.abs(vMax) * 0.02 || 1)
    const lo = vMin - pad
    const hi = vMax + pad
    const spanDays = (tMax - tMin) / 86_400_000

    const iw = Math.max(40, width - M.left - M.right)
    const ih = height - M.top - M.bottom
    const X = (t: string) => M.left + ((new Date(t).getTime() - tMin) / (tMax - tMin)) * iw
    const Y = (v: number) => M.top + (1 - (v - lo) / (hi - lo)) * ih

    let xt = 6
    if (spanDays > 400) xt = 5
    else if (spanDays > 200) xt = 7
    const xs = Array.from({ length: xt }, (_, i) =>
      all.length ? all[Math.min(all.length - 1, Math.floor((i * all.length) / xt))].ts : ''
    )

    return {
      x: X,
      y: Y,
      xTicks: Array.from(new Set(xs)),
      yTicks: ticks(lo, hi, 5),
      spanDays,
      iw,
      lo,
    }
  }, [data, trend, forecast, width, height, minimal]) // eslint-disable-line react-hooks/exhaustive-deps

  const hasTrend = (trend?.length ?? 0) > 1
  const hasForecast = (forecast?.length ?? 0) > 0
  const hasBand = forecast?.some((p) => p.lower != null || p.upper != null) ?? false
  const showLegend = !minimal && (hasTrend || hasForecast)

  const gridLines = !minimal
    ? yTicks.map((t, i) => (
        <g key={`g${i}`}>
          <line
            x1={M.left}
            x2={width - M.right}
            y1={y(t)}
            y2={y(t)}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
          <text
            x={M.left - 8}
            y={y(t) + 3.5}
            textAnchor="end"
            fontSize={11}
            fill="var(--ink-mute)"
            style={{ fontFamily: 'var(--font-mono)', fontFeatureSettings: "'tnum'" }}
          >
            {formatY ? formatY(t) : fmtCompact(t)}
          </text>
        </g>
      ))
    : null

  const xLabels = !minimal
    ? xTicks.map((ts, i) => (
        <text key={`x${i}`} x={x(ts)} y={height - 8} textAnchor="middle" fontSize={11} fill="var(--ink-mute)" style={{ fontFamily: 'var(--font-mono)', fontFeatureSettings: "'tnum'" }}>
          {fmtDate(ts, spanDays)}
        </text>
      ))
    : null

  const areaFull = useMemo(() => {
    if (data.length === 0) return ''
    const line = smoothPath(toPts(data), x, y)
    const last = data[data.length - 1]
    const first = data[0]
    return `${line} L ${x(last.timestamp).toFixed(2)} ${y(Math.min(0, lo)).toFixed(2)} L ${x(
      first.timestamp
    ).toFixed(2)} ${y(Math.min(0, lo)).toFixed(2)} Z`
  }, [data, x, y, lo])

  const forecastBand = useMemo(() => {
    if (!forecast || forecast.length < 2) return ''
    const u = smoothPath(
      forecast.map((p) => ({ ts: p.timestamp, v: p.upper ?? p.value })),
      x,
      y
    )
    const l = smoothPath(
      [...forecast].reverse().map((p) => ({ ts: p.timestamp, v: p.lower ?? p.value })),
      x,
      y
    )
    return `${u} L ${x(forecast[forecast.length - 1].timestamp).toFixed(2)} ${y(
      forecast[forecast.length - 1].lower ?? forecast[forecast.length - 1].value
    ).toFixed(2)} ${l} Z`
  }, [forecast, x, y])

  const hoverIndex = hover != null ? Math.min(hover, data.length - 1) : null
  const hoverPoint = hoverIndex != null && hoverIndex >= 0 ? data[hoverIndex] : null
  const hoverAnomaly = hoverPoint
    ? anomalies?.find(
        (a) => new Date(a.timestamp).getTime() === new Date(hoverPoint.timestamp).getTime()
      )
    : null
  const hoverForecast = hoverPoint
    ? forecast?.find(
        (p) => new Date(p.timestamp).getTime() === new Date(hoverPoint.timestamp).getTime()
      )
    : null

  function onMove(e: React.MouseEvent) {
    if (minimal || data.length === 0) return
    const rect = wrapRef.current?.getBoundingClientRect()
    if (!rect) return
    const px = ((e.clientX - rect.left) / rect.width) * width
    const frac = Math.max(0, Math.min(1, (px - M.left) / iw))
    setHover(Math.round(frac * (data.length - 1)))
  }

  const crossX = hoverPoint ? x(hoverPoint.timestamp) : 0
  const tooltipLeft = hoverPoint ? Math.min(Math.max(crossX + 12, 8), width - 230) : 0
  const tooltipTop = hoverPoint ? y(hoverPoint.value) - 14 : 0

  const legend = showLegend ? (
    <div className="row" style={{ gap: 16, marginBottom: 10, flexWrap: 'wrap' }}>
      {!hasTrend && !hasForecast && (
        <span className="row" style={{ gap: 6, fontSize: 12, color: 'var(--ink-mute)' }}>
          <span style={{ width: 14, height: 2.5, borderRadius: 2, background: 'var(--primary)' }} />
          Series
        </span>
      )}
      {hasTrend && (
        <span className="row" style={{ gap: 6, fontSize: 12, color: 'var(--ink-mute)' }}>
          <span
            style={{
              width: 14,
              height: 0,
              borderTop: '2px dashed var(--ruby)',
              display: 'inline-block',
            }}
          />
          Trend
        </span>
      )}
      {hasForecast && (
        <span className="row" style={{ gap: 6, fontSize: 12, color: 'var(--ink-mute)' }}>
          <span
            style={{
              width: 14,
              height: 2.5,
              borderRadius: 2,
              background: 'var(--primary-deep)',
              opacity: 0.7,
            }}
          />
          Forecast{hasBand ? ' (95% band)' : ''}
        </span>
      )}
      {(anomalies?.length ?? 0) > 0 && (
        <span className="row" style={{ gap: 6, fontSize: 12, color: 'var(--ink-mute)' }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: 'var(--ruby)',
              display: 'inline-block',
            }}
          />
          Anomalies
        </span>
      )}
    </div>
  ) : null

  return (
    <div>
      {legend}
      <div
        ref={wrapRef}
        style={{ position: 'relative', width: '100%' }}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        <svg
          width={width}
          height={height}
          role="img"
          aria-label="Time series chart"
          style={{ display: 'block' }}
          shapeRendering="geometricPrecision"
        >
          <defs>
            <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={minimal ? 0.24 : 0.16} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={minimal ? 0.02 : 0.01} />
            </linearGradient>
          </defs>
          {gridLines}
          {xLabels}
          {forecastBand && (
            <path d={forecastBand} fill={hasBand ? 'var(--primary)' : 'none'} opacity={hasBand ? 0.1 : 0} />
          )}
          {areaFull && <path d={areaFull} fill="url(#areaFill)" stroke="none" />}
          {data.length > 1 && (
            <path
              d={smoothPath(toPts(data), x, y)}
              fill="none"
              stroke="var(--primary)"
              strokeWidth={minimal ? 1.6 : 2}
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          )}
          {hasTrend && (
            <path
              d={smoothPath(toPts(trend!), x, y)}
              fill="none"
              stroke="var(--ruby)"
              strokeWidth={1.5}
              strokeDasharray="5 4"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          )}
          {hasForecast && (
            <path
              d={smoothPath(toFPts(forecast!), x, y)}
              fill="none"
              stroke="var(--primary-deep)"
              strokeWidth={2}
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          )}
          {(anomalies ?? []).map((a, i) => {
            const c = a.severity === 'critical' ? 'var(--accent)' : 'var(--ruby)'
            const selected = selAnomaly?.index === i
            const interactive = datasetId != null
            const select = () =>
              setSelAnomaly(selected ? null : { anomaly: a, index: i })
            return (
              <g key={`a${i}`}>
                <circle
                  cx={x(a.timestamp)}
                  cy={y(a.value)}
                  r={selected ? 12 : 9}
                  fill={c}
                  opacity={selected ? 0.28 : 0.18}
                />
                <circle
                  cx={x(a.timestamp)}
                  cy={y(a.value)}
                  r={4.5}
                  fill={c}
                  stroke="#0a0a0f"
                  strokeWidth={1.5}
                  role={interactive ? 'button' : undefined}
                  tabIndex={interactive ? 0 : undefined}
                  aria-label={interactive ? 'Show related signals for this anomaly' : undefined}
                  onClick={interactive ? select : undefined}
                  onKeyDown={
                    interactive
                      ? (e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            select()
                          }
                        }
                      : undefined
                  }
                  style={interactive ? { cursor: 'pointer' } : undefined}
                >
                  <title>{`${a.direction} · ${fmtCompact(a.value)} · ${a.reason}`}</title>
                </circle>
              </g>
            )
          })}
          {hoverIndex != null && hoverIndex >= 0 && (
            <line
              x1={crossX}
              x2={crossX}
              y1={M.top}
              y2={height - M.bottom}
              stroke="var(--ink-mute)"
              strokeWidth={1}
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>

        {hoverPoint && !minimal && (
          <div
            className="chart-tip"
            style={{
              position: 'absolute',
              top: Math.max(2, tooltipTop),
              left: tooltipLeft,
              transform: 'translateY(-100%)',
              pointerEvents: 'none',
              background: 'var(--surface-2)',
              color: 'var(--ink)',
              borderRadius: 10,
              padding: '9px 12px',
              fontSize: 12,
              boxShadow: '0 12px 30px rgba(0,0,0,0.5), 0 0 0 1px var(--hairline)',
              zIndex: 5,
              minWidth: 150,
            }}
          >
            <div style={{ color: 'var(--ink-mute)', marginBottom: 3, fontFamily: 'var(--font-mono)', fontSize: 11 }}>
              {fmtDate(hoverPoint.timestamp, spanDays)}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontFeatureSettings: "'tnum'", fontWeight: 500 }}>
              {formatY ? formatY(hoverPoint.value) : fmtCompact(hoverPoint.value)}
            </div>
            {hoverAnomaly && (
              <div style={{ color: 'var(--accent)', marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                {hoverAnomaly.direction} · {hoverAnomaly.reason}
              </div>
            )}
            {hoverForecast && hasBand && hoverForecast.lower != null && (
              <div style={{ color: 'var(--ink-mute)', marginTop: 2, fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                band {fmtCompact(hoverForecast.lower ?? 0)} – {fmtCompact(hoverForecast.upper ?? 0)}
              </div>
            )}
          </div>
        )}
      </div>

      {!minimal && selAnomaly && datasetId != null && (
        <div
          style={{
            marginTop: 12,
            border: '1px solid var(--hairline)',
            borderRadius: 'var(--r-lg)',
            background: 'var(--surface-2)',
            padding: '10px 12px',
          }}
        >
          <div
            className="row"
            style={{ justifyContent: 'space-between', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}
          >
            <span className="row" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: selAnomaly.anomaly.severity === 'critical' ? 'var(--accent)' : 'var(--ruby)',
                  display: 'inline-block',
                }}
              />
              <span className="num" style={{ fontSize: 12 }}>
                {fmtDate(selAnomaly.anomaly.timestamp, spanDays)}
              </span>
              <span style={{ fontSize: 12, color: 'var(--ink-mute)' }}>
                {selAnomaly.anomaly.direction} — related signals
              </span>
            </span>
            <button className="btn btn-ghost btn-sm" onClick={() => setSelAnomaly(null)}>
              Close
            </button>
          </div>
          <RelatedSignalsPanel datasetId={datasetId} anomalyId={selAnomaly.index} />
        </div>
      )}
    </div>
  )
}
