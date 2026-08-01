import { request } from './http'
import type { AlertRuleCreate, AlertRuleOut, AlertRuleUpdate, Message, Paginated } from '../types'

export const alertRulesApi = {
  createAlertRule: (payload: AlertRuleCreate) =>
    request<AlertRuleOut>('/alert-rules', { method: 'POST', body: JSON.stringify(payload) }),
  listAlertRules: (dataset_id?: number) =>
    request<Paginated<AlertRuleOut>>(
      `/alert-rules?limit=100${dataset_id != null ? `&dataset_id=${dataset_id}` : ''}`
    ),
  updateAlertRule: (id: number, payload: AlertRuleUpdate) =>
    request<AlertRuleOut>(`/alert-rules/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteAlertRule: (id: number) =>
    request<Message>(`/alert-rules/${id}`, { method: 'DELETE' }),
}
