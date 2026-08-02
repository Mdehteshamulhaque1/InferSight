import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { AutoImportResult, PreviewReport } from '../types'
import { usePageTitle } from '../hooks/usePageTitle'
import { useToast } from '../components/ui/Toast'
import { Dropzone } from '../components/ui/Dropzone'
import {
  IconArrowLeft,
  IconArrowRight,
  IconCheck,
  IconCheckCircle,
  IconFile,
  IconSparkles,
} from '../components/ui/icons'

type Step = 'upload' | 'detect' | 'preview' | 'analyzing' | 'done'

const STEPS = [
  { n: 1, label: 'Upload' },
  { n: 2, label: 'Preview' },
  { n: 3, label: 'Insights' },
]

function stepIndex(step: Step): number {
  if (step === 'upload') return 0
  if (step === 'detect' || step === 'preview') return 1
  return 2
}

export function Upload() {
  const navigate = useNavigate()
  const location = useLocation()
  const toast = useToast()
  usePageTitle('Upload your data')

  const [step, setStep] = useState<Step>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [report, setReport] = useState<PreviewReport | null>(null)
  const [result, setResult] = useState<AutoImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const initialFile = (location.state as { file?: File } | null)?.file

  useEffect(() => {
    if (initialFile) void pickFile(initialFile)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function pickFile(f: File) {
    setFile(f)
    setError(null)
    setReport(null)
    setStep('detect')
    try {
      const rep = await api.previewAny(f)
      setReport(rep)
      setStep('preview')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not read that file')
      setStep('upload')
    }
  }

  async function analyze() {
    if (!file) return
    setStep('analyzing')
    setError(null)
    try {
      const res = await api.autoImport(file)
      setResult(res)
      setStep('done')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
      setStep('preview')
      toast.push(e instanceof Error ? e.message : 'Analysis failed', 'err')
    }
  }

  const idx = stepIndex(step)
  const sample = report?.sample ?? []

  return (
    <div className="wizard">
      <div className="page-head">
        <div>
          <h1>Upload your data</h1>
          <p className="sub">We detect everything automatically — no setup required.</p>
        </div>
      </div>

      <div className="wizard-progress" role="tablist" aria-label="Upload progress">
        {STEPS.map((s, i) => (
          <div key={s.n} className="wizard-step-wrap">
            <div className={`wizard-step${i < idx ? ' done' : i === idx ? ' active' : ''}`}>
              {i < idx ? <IconCheck size={13} /> : s.n}
            </div>
            <span className={`wizard-label${i === idx ? ' active' : ''}`}>{s.label}</span>
            {i < STEPS.length - 1 && <div className="wizard-line" />}
          </div>
        ))}
      </div>

      {step === 'upload' && (
        <div className="card wizard-card">
          <div className="wizard-hero">
            <h2>Welcome to InferSight</h2>
            <p>Drop a CSV and we’ll build the analysis for you.</p>
          </div>
          <Dropzone className="wizard-dropzone" onFile={(f) => void pickFile(f)} />
          {error && <div className="field-error mt-4">{error}</div>}
          <div className="row mt-6" style={{ gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
            <span className="pill pill-green"><IconCheckCircle size={12} /> Auto column detection</span>
            <span className="pill pill-green"><IconCheckCircle size={12} /> Granularity & metric inferred</span>
            <span className="pill pill-green"><IconCheckCircle size={12} /> No forms</span>
          </div>
        </div>
      )}

      {(step === 'detect' || step === 'preview') && report && (
        <div className="card wizard-card">
          <div className="wizard-hero">
            <h2><span className="wizard-file"><IconFile size={18} /> {report.filename}</span></h2>
            <p>Here’s what we found in your file.</p>
          </div>

          <div className="wizard-checks">
            {[
              ['Date column found', report.timestamp_column],
              ['Value column found', report.value_column],
              ['Rows ready', report.parsed_points.toLocaleString()],
              ['Granularity', `${report.detected_granularity} data`],
              ['Ready', 'Looks great'],
            ].map(([label, value]) => (
              <div key={label} className="wizard-check">
                <span className="wizard-check-ico"><IconCheck size={13} /></span>
                <span className="wizard-check-label">{label}</span>
                <span className="wizard-check-value num">{value}</span>
              </div>
            ))}
          </div>

          {sample.length > 0 && (
            <div className="table-wrap table-scroll mt-6">
              <table className="table">
                <thead>
                  <tr>
                    <th>{report.timestamp_column}</th>
                    <th>{report.value_column}</th>
                  </tr>
                </thead>
                <tbody>
                  {sample.map((p) => (
                    <tr key={p.timestamp}>
                      <td className="num">{p.timestamp}</td>
                      <td className="num">{p.value.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {error && <div className="field-error mt-4">{error}</div>}

          <div className="row mt-6" style={{ justifyContent: 'space-between', gap: 10 }}>
            <button className="btn btn-secondary" onClick={() => setStep('upload')}>
              <IconArrowLeft size={14} /> Change file
            </button>
            <button className="btn btn-primary wizard-cta" onClick={() => void analyze()}>
              <IconSparkles size={15} /> Analyze dataset
              <IconArrowRight size={14} />
            </button>
          </div>
        </div>
      )}

      {step === 'analyzing' && (
        <div className="card wizard-card wizard-center">
          <span className="spinner wizard-spinner" />
          <h2>Analyzing…</h2>
          <p className="muted">Building your dataset, detecting anomalies, and running the forecast.</p>
        </div>
      )}

      {step === 'done' && result && (
        <div className="card wizard-card wizard-center">
          <span className="wizard-done-ico"><IconCheck size={22} /></span>
          <h2><span className="wizard-file">{result.dataset.name}</span> is ready</h2>
          <p className="muted" style={{ maxWidth: 420 }}>
            Imported {result.result.inserted.toLocaleString()} point
            {result.result.inserted === 1 ? '' : 's'} · {result.result.detected_granularity}{' '}
            granularity · detected column “{result.result.value_column}”.
          </p>
          <div className="row" style={{ gap: 10, marginTop: 8 }}>
            <button className="btn btn-primary" onClick={() => navigate('/app/dashboard')}>
              Open dashboard <IconArrowRight size={14} />
            </button>
            <Link className="btn btn-secondary" to={`/app/datasets/${result.dataset.id}`}>
              Dataset settings
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
