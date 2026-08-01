import { request } from './http'
import type {
  BulkResult,
  DatasetCreateInput,
  DatasetRead,
  Message,
  MetricPointInput,
  Paginated,
  PointRead,
} from '../types'

export const datasetsApi = {
  listDatasets: (page = 1, limit = 50) =>
    request<Paginated<DatasetRead>>(`/datasets?page=${page}&limit=${limit}`),
  getDataset: (id: number) => request<DatasetRead>(`/datasets/${id}`),
  createDataset: (payload: DatasetCreateInput) =>
    request<DatasetRead>('/datasets', { method: 'POST', body: JSON.stringify(payload) }),
  deleteDataset: (id: number) =>
    request<Message>(`/datasets/${id}`, { method: 'DELETE' }),
  listPoints: (id: number, limit = 500) =>
    request<Paginated<PointRead>>(`/datasets/${id}/points?limit=${limit}`),
  ingestPoints: (id: number, points: MetricPointInput[]) =>
    request<BulkResult>(`/datasets/${id}/points`, {
      method: 'POST',
      body: JSON.stringify({ points }),
    }),
}
