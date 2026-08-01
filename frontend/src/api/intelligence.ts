import { request } from './http'
import type {
  ChatOut,
  DatasetVersionOut,
  HealthScoreOut,
  Kpi,
  Message,
  Paginated,
  ProfileOut,
  RecommendationOut,
  RelatedSignalOut,
  RootCauseOut,
} from '../types'

export const intelligenceApi = {
  profile: (id: number) => request<ProfileOut>(`/datasets/${id}/profile`),
  discoverKpis: (id: number) => request<Kpi[]>(`/datasets/${id}/kpis/discover`),
  recommendations: (id: number) =>
    request<RecommendationOut[]>(`/datasets/${id}/recommendations`),
  health: (id: number) => request<HealthScoreOut>(`/datasets/${id}/health`),
  rootCause: (id: number) => request<RootCauseOut>(`/datasets/${id}/root-cause`),
  chat: (message: string, dataset_id?: number | null) =>
    request<ChatOut>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, dataset_id: dataset_id ?? null }),
    }),
  getRelatedSignals: (datasetId: number, anomalyId: number) =>
    request<RelatedSignalOut[] | { related_signals: RelatedSignalOut[] }>(
      `/datasets/${datasetId}/anomalies/${anomalyId}/related`
    ).then((res) => (Array.isArray(res) ? res : res.related_signals)),
  listVersions: (id: number, limit = 20) =>
    request<Paginated<DatasetVersionOut>>(`/datasets/${id}/versions?limit=${limit}`),
  rollbackVersion: (id: number, versionNo: number) =>
    request<Message>(`/datasets/${id}/versions/${versionNo}/rollback`, { method: 'POST' }),
}
