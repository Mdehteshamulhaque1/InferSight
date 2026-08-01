import { request } from './http'
import type { AnalyticsResponse } from '../types'

export const analyticsApi = {
  analytics: (id: number) => request<AnalyticsResponse>(`/analytics/datasets/${id}`),
}
