import { request } from './http'
import type { AnomalyResponse } from '../types'

export const anomaliesApi = {
  anomalies: (id: number, threshold = 3, window = 7) =>
    request<AnomalyResponse>(
      `/anomalies/datasets/${id}?threshold=${threshold}&window=${window}`
    ),
}
