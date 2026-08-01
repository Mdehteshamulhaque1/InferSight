import { useEffect } from 'react'

export function usePageTitle(title: string): void {
  useEffect(() => {
    const base = 'InferSight'
    document.title = title ? `${title} — ${base}` : base
  }, [title])
}
