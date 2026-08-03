import { uploadFile } from './http'
import type { AutoImportResult, IngestResult, PreviewReport } from '../types'

export const ingestionApi = {
  previewIngest: (id: number, file: File) =>
    uploadFile<{ parsed_points: number; dropped: number; columns: string[] }>(
      `/ingest/${id}/preview`,
      file
    ),
  ingestFile: (id: number, file: File, replace = false) =>
    uploadFile<IngestResult>(`/ingest/${id}/file`, file, replace ? { replace: 'true' } : undefined),
  previewAny: (file: File) => uploadFile<PreviewReport>('/ingest/preview', file),
  autoImport: (file: File) => uploadFile<AutoImportResult>('/ingest/auto', file),
}
