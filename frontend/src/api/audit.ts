import { request } from './http'
import type { AuditEventOut, Paginated } from '../types'

export const auditApi = {
  listAudit: (limit = 50, resourceId?: number) =>
    request<Paginated<AuditEventOut>>(
      `/audit?limit=${limit}${resourceId != null ? `&resource_id=${resourceId}` : ''}`
    ),
}
