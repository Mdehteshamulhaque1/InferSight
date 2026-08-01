import { request } from './http'
import type { AlertDeliveryOut, AlertOut, Message, Paginated } from '../types'

export const alertsApi = {
  listAlerts: (unreadOnly = false, limit = 50) =>
    request<Paginated<AlertOut>>(`/alerts?limit=${limit}${unreadOnly ? '&unread_only=true' : ''}`),
  unreadAlerts: () => request<{ count: number }>('/alerts/unread-count'),
  markAlertRead: (id: number) =>
    request<AlertOut>(`/alerts/${id}/read`, { method: 'POST' }),
  markAllAlertsRead: () => request<Message>('/alerts/read-all', { method: 'POST' }),
  syncAlerts: (id: number) =>
    request<{ dataset_id: number; anomalies: number; critical: number; alerts_created: number }>(
      `/alerts/sync/${id}`,
      { method: 'POST' }
    ),
  listAlertDeliveries: (alertId: number, limit = 50) =>
    request<Paginated<AlertDeliveryOut>>(`/alerts/${alertId}/deliveries?limit=${limit}`),
}
