import type { TokenPair } from '../types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1'

const TOKEN_KEY = 'infersight.access'
const REFRESH_KEY = 'infersight.refresh'

export function getTokens(): { access: string; refresh: string } | null {
  const access = localStorage.getItem(TOKEN_KEY)
  const refresh = localStorage.getItem(REFRESH_KEY)
  if (!access || !refresh) return null
  return { access, refresh }
}

export function setTokens(t: TokenPair): void {
  localStorage.setItem(TOKEN_KEY, t.access_token)
  localStorage.setItem(REFRESH_KEY, t.refresh_token)
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let detail = `Request failed (${res.status})`
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') detail = body.detail
    else if (Array.isArray(body.detail)) {
      detail = body.detail
        .map((d: { msg?: string; loc?: (string | number)[] }) =>
          d.loc ? `${d.loc.join('.')}: ${d.msg ?? ''}` : (d.msg ?? '')
        )
        .join('; ')
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, detail)
}

async function rawFetch(path: string, init?: RequestInit): Promise<Response> {
  const tokens = getTokens()
  const headers = new Headers(init?.headers)
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (tokens) headers.set('Authorization', `Bearer ${tokens.access}`)
  return fetch(`${BASE}${path}`, { ...init, headers })
}

async function refreshTokens(): Promise<boolean> {
  const tokens = getTokens()
  if (!tokens) return false
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: tokens.refresh }),
    })
    if (!res.ok) return false
    const pair: TokenPair = await res.json()
    setTokens(pair)
    return true
  } catch {
    return false
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res = await rawFetch(path, init)
  if (res.status === 401 && !path.startsWith('/auth/login') && !path.startsWith('/auth/register')) {
    if (await refreshTokens()) {
      res = await rawFetch(path, init)
    }
  }
  if (!res.ok) throw await parseError(res)
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

export async function requestBlob(path: string): Promise<{ blob: Blob; filename: string }> {
  let res = await rawFetch(path)
  if (res.status === 401) {
    if (await refreshTokens()) res = await rawFetch(path)
  }
  if (!res.ok) throw await parseError(res)
  const blob = await res.blob()
  const header = res.headers.get('Content-Disposition') ?? ''
  const match = /filename="([^"]+)"/.exec(header)
  return { blob, filename: match?.[1] ?? 'report' }
}

export async function uploadFile<T>(
  path: string,
  file: File,
  extra?: Record<string, string>
): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  const params = extra ? `?${new URLSearchParams(extra)}` : ''
  let res = await rawFetch(`${path}${params}`, { method: 'POST', body: form })
  if (res.status === 401) {
    if (await refreshTokens()) {
      res = await rawFetch(`${path}${params}`, { method: 'POST', body: form })
    }
  }
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as T
}
