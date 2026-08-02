import { useRef, useState } from 'react'
import type { ChangeEvent, ReactNode } from 'react'
import { IconUpload } from './icons'

export function Dropzone({
  onFile,
  icon,
  title = 'Drop your data here',
  subtitle = 'or click to browse · .csv, .xlsx, .xls, .json',
  compact = false,
  className = '',
}: {
  onFile: (f: File) => void
  icon?: ReactNode
  title?: ReactNode
  subtitle?: ReactNode
  compact?: boolean
  className?: string
}) {
  const [drag, setDrag] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <div
      className={`dropzone${drag ? ' drag' : ''}${compact ? ' compact' : ''} ${className}`.trim()}
      role="button"
      tabIndex={0}
      aria-label="Upload a data file"
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
      }}
      onDragOver={(e) => {
        e.preventDefault()
        setDrag(true)
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDrag(false)
        const f = e.dataTransfer.files?.[0]
        if (f) onFile(f)
      }}
    >
      <span className="ico wizard-drop-icon">{icon ?? <IconUpload size={22} />}</span>
      <span className="fname wizard-drop-title">{title}</span>
      {subtitle && <span className="fsub">{subtitle}</span>}
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx,.xls,.json"
        onChange={(e: ChangeEvent<HTMLInputElement>) => {
          const f = e.target.files?.[0]
          if (f) onFile(f)
        }}
      />
    </div>
  )
}
