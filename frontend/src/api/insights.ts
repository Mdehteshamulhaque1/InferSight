import { request } from './http'
import type { InsightOut, Message, Paginated } from '../types'

export const insightsApi = {
  listInsights: (page = 1, limit = 50) =>
    request<Paginated<InsightOut>>(`/insights?page=${page}&limit=${limit}`),
  generateInsight: (id: number) =>
    request<InsightOut>(`/insights/datasets/${id}`, { method: 'POST' }),
  deleteInsight: (id: number) =>
    request<Message>(`/insights/${id}`, { method: 'DELETE' }),
}
