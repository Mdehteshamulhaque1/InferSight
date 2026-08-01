import { requestBlob } from './http'

export const reportsApi = {
  exportReport: (id: number, ext: 'csv' | 'xlsx' | 'pdf') =>
    requestBlob(`/reports/datasets/${id}.${ext}`),
}
