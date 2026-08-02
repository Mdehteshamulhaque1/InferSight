import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { DatasetRead } from '../types'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import { useToast } from '../components/ui/Toast'
import { IconDownload, IconFile } from '../components/ui/icons'
import { fmtDate } from '../lib/format'

type Ext = 'csv' | 'xlsx' | 'pdf'

export function Reports() {
  const toast = useToast()
  usePageTitle('Reports')
  const datasets = useAsync(() => api.listDatasets(1, 100), [])
  const [busyId, setBusyId] = useState<number | null>(null)

  const list = datasets.data?.items ?? []

  async function exportAs(d: DatasetRead, ext: Ext) {
    setBusyId(d.id)
    try {
      const { blob, filename } = await api.exportReport(d.id, ext)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast.push(`Exported ${filename}`)
    } catch (e) {
      toast.push(e instanceof Error ? e.message : 'Export failed', 'err')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Reports</h1>
          <p className="sub">One-click exports of your datasets, forecasts, and anomaly runs.</p>
        </div>
      </div>

      <div className="card">
        {datasets.loading ? (
          <div className="empty"><span className="spinner" /></div>
        ) : list.length === 0 ? (
          <div className="empty">
            <span className="empty-state">
              <span className="ico"><IconFile size={20} /></span>
              <h3>No datasets to export yet</h3>
              <p>Upload a dataset first, then export its data as CSV, XLSX, or PDF.</p>
              <Link className="btn btn-primary mt-4" to="/app/upload">
                Upload your data
              </Link>
            </span>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Points</th>
                  <th>Granularity</th>
                  <th>Last point</th>
                  <th style={{ textAlign: 'right' }}>Export</th>
                </tr>
              </thead>
              <tbody>
                {list.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <div className="strong">{d.name}</div>
                      <div className="muted mono" style={{ fontSize: 12 }}>/{d.slug}</div>
                    </td>
                    <td className="num">{d.point_count.toLocaleString()}</td>
                    <td className="num">{d.granularity}</td>
                    <td className="num">{fmtDate(d.last_point_at)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div className="row" style={{ gap: 4, justifyContent: 'flex-end' }}>
                        {(['csv', 'xlsx', 'pdf'] as Ext[]).map((ext) => (
                          <button
                            key={ext}
                            className="btn btn-ghost btn-sm"
                            disabled={busyId === d.id}
                            title={`Export ${ext.toUpperCase()}`}
                            onClick={() => void exportAs(d, ext)}
                          >
                            {busyId === d.id ? <span className="spinner" /> : <IconDownload size={13} />}
                            {ext.toUpperCase()}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
