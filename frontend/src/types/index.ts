export interface UserRead {
  id: number
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface DatasetRead {
  id: number
  name: string
  slug: string
  description?: string | null
  metric_type: string
  unit: string
  currency?: string
  granularity: string
  is_active: boolean
  created_at: string
  updated_at: string
  last_import_at?: string | null
  point_count: number
  last_point_at?: string | null
}

export interface PointRead {
  id: number
  dataset_id: number
  timestamp: string
  value: number
}

export interface BulkResult {
  dataset_id: number
  inserted: number
  skipped_duplicates: number
  total: number
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface Kpi {
  key: string
  label: string
  value: number
  unit: string
  change_pct?: number | null
  metadata?: Record<string, unknown> | null
}

export interface SeriesPoint {
  timestamp: string
  value: number
}

export interface Trend {
  slope: number
  intercept: number
  r_squared: number
  direction: string
  fitted: SeriesPoint[]
}

export interface AnalyticsResponse {
  dataset: DatasetRead
  kpis: Kpi[]
  series: SeriesPoint[]
  trend: Trend
  period?: { start: string; end: string } | null
}

export interface Anomaly {
  timestamp: string
  value: number
  expected: number
  score: number
  severity: string
  direction: string
  reason: string
}

export interface AnomalyResponse {
  dataset_id: number
  method: string
  window: number
  threshold: number
  total_points: number
  anomalies: Anomaly[]
  summary: Record<string, number>
}

export interface ForecastPoint {
  timestamp: string
  value: number
  lower?: number | null
  upper?: number | null
}

export interface ForecastMetrics {
  method: string
  mape?: number | null
  mae?: number | null
  rmse?: number | null
  holdout_points: number
}

export interface ForecastResponse {
  dataset_id: number
  horizon: number
  method: string
  seasonality: boolean
  metrics: ForecastMetrics
  points: ForecastPoint[]
}

export interface InsightOut {
  id: number
  dataset_id?: number | null
  kind: string
  severity: string
  title: string
  body: string
  payload?: Record<string, unknown> | null
  created_at: string
}

export interface Message {
  detail: string
}

export interface MetricPointInput {
  timestamp: string
  value: number
}

export interface DatasetCreateInput {
  name: string
  slug?: string
  description?: string
  metric_type: string
  unit?: string
  currency?: string
  granularity: string
}

// ---------------------------------------------------------------------------
// Intelligence
// ---------------------------------------------------------------------------

export interface ProfileOut {
  count: number
  start: string | null
  end: string | null
  span_days: number
  stats: {
    min: number
    max: number
    mean: number
    median: number
    std: number
    sum: number
    cv: number
  }
  trend: {
    slope_per_period_pct: number
    direction: string
    r_squared: number
  }
  seasonality: { lag: number; correlation: number; strength: string }
  quality: {
    completeness_pct: number
    expected_points: number
    missing_periods: number
    duplicate_timestamps: number
    negative_count: number
    zero_count: number
    freshness_hours: number
  }
  top_points: SeriesPoint[]
  bottom_points: SeriesPoint[]
  biggest_movers: {
    from: string
    to: string
    from_value: number
    to_value: number
    change_pct: number
  }[]
}

export interface RootCauseOut {
  timestamp: string
  actual: number
  expected: number
  delta: number
  delta_pct: number
  direction: string
  contributing_segments: {
    dimension: string
    segment: string
    value: number
    baseline: number
    change_pct: number
    weight: number
  }[]
  time_effects: { factor: string; value: string; relative_change_pct: number; points: number }[]
  hypotheses: { title: string; evidence: string; confidence: string }[]
}

export interface RecommendationOut {
  id: string
  severity: string
  category: string
  action: string
  rationale: string
  impact: string
}

export interface HealthComponent {
  key: string
  label: string
  score: number
  weight: number
  detail: string
}

export interface HealthScoreOut {
  score: number
  grade: string
  verdict: string
  components: HealthComponent[]
}

export interface ChatOut {
  intent: string
  reply: string
  data: Record<string, unknown> | null
  followups: string[]
}

export interface AnalysisSummary {
  dataset_id: number
  name: string
  currency: string | null
  granularity: string
  kpis: {
    key: string
    label: string
    value: number
    unit?: string
    change_pct?: number | null
  }[]
  trend: {
    direction: string
    slope_per_period_pct: number
    r_squared: number
  }
  anomaly_count: number
  critical_anomalies: number
  forecast: {
    method: string
    horizon: number
    seasonality: boolean
    mape?: number | null
    points: { timestamp: string; value: number; lower?: number | null; upper?: number | null }[]
  } | null
  health: { score: number; grade: string; verdict: string }
}

export interface AlertOut {
  id: number
  dataset_id?: number | null
  kind: string
  severity: string
  title: string
  body: string
  is_read: boolean
  created_at: string
}

export type SeverityLevel = 'warning' | 'critical'
export type AlertChannelValue = 'email' | 'slack' | 'webhook'
export type DeliveryStatusValue = 'pending' | 'sent' | 'failed'

export interface AlertRuleCreate {
  dataset_id: number
  severity_threshold: SeverityLevel
  channels: AlertChannelValue[]
  cooldown_minutes: number
  is_active: boolean
  webhook_url?: string | null
}

export interface AlertRuleUpdate {
  severity_threshold?: SeverityLevel
  channels?: AlertChannelValue[]
  cooldown_minutes?: number
  is_active?: boolean
  webhook_url?: string | null
}

export interface AlertRuleOut {
  id: number
  dataset_id: number
  severity_threshold: SeverityLevel
  channels: AlertChannelValue[]
  cooldown_minutes: number
  is_active: boolean
  webhook_url: string | null
  created_at: string
}

export interface AlertDeliveryOut {
  id: number
  alert_id: number
  rule_id: number | null
  channel: string
  status: DeliveryStatusValue
  error_message: string | null
  sent_at: string | null
  created_at: string
}

export interface RelatedSignalOut {
  dataset_id: number
  dataset_name: string
  correlation: number
  direction: 'same' | 'opposite'
}

export interface DatasetVersionOut {
  id: number
  dataset_id: number
  version_no: number
  user_id: number
  source: string
  points_added: number
  points_removed: number
  total_after: number
  filename?: string | null
  status: string
  created_at: string
}

export interface AuditEventOut {
  id: number
  user_id?: number | null
  action: string
  resource_type: string
  resource_id?: number | null
  details?: Record<string, unknown> | null
  created_at: string
}

export interface IngestResult {
  dataset_id: number
  filename: string
  columns: string[]
  timestamp_column: string
  value_column: string
  detected_granularity: string
  parsed_points: number
  inserted: number
  skipped_duplicates: number
  dropped: number
  replaced: boolean
  point_count: number
}

export interface PreviewReport {
  filename: string
  columns: string[]
  timestamp_column: string
  value_column: string
  detected_granularity: string
  parsed_points: number
  dropped: number
  sample: { timestamp: string; value: number; meta?: Record<string, unknown> | null }[]
}

export interface AutoImportResult {
  dataset: DatasetRead
  result: IngestResult
}
