import { alertRulesApi } from './alertRules'
import { alertsApi } from './alerts'
import { analyticsApi } from './analytics'
import { anomaliesApi } from './anomalies'
import { auditApi } from './audit'
import { authApi } from './auth'
import { datasetsApi } from './datasets'
import { forecastsApi } from './forecasts'
import { ingestionApi } from './ingestion'
import { insightsApi } from './insights'
import { intelligenceApi } from './intelligence'
import { reportsApi } from './reports'

export { ApiError, clearTokens, getTokens, setTokens } from './http'

export const api = {
  ...authApi,
  ...datasetsApi,
  ...analyticsApi,
  ...anomaliesApi,
  ...forecastsApi,
  ...insightsApi,
  ...reportsApi,
  ...intelligenceApi,
  ...ingestionApi,
  ...auditApi,
  ...alertsApi,
  ...alertRulesApi,
}
