import type {
  LoginResponse,
  SampleCase,
  ScanChatRequest,
  ScanChatResponse,
  ShredResponse,
  StudyAnalysisResponse,
  User,
  WorklistEntry,
} from '@/types/clinical'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const HAS_URL_SCHEME_RE = /^[a-z][a-z0-9+.-]*:/i

let inMemoryToken: string | null = null

export function getAuthToken(): string | null {
  if (inMemoryToken) return inMemoryToken
  if (typeof window !== 'undefined' && window.sessionStorage) {
    inMemoryToken = window.sessionStorage.getItem('medshield_auth_token')
  }
  return inMemoryToken
}

export function setAuthToken(token: string | null): void {
  inMemoryToken = token
  if (typeof window !== 'undefined' && window.sessionStorage) {
    if (token) {
      window.sessionStorage.setItem('medshield_auth_token', token)
    } else {
      window.sessionStorage.removeItem('medshield_auth_token')
    }
  }
}

/**
 * Returns the configured backend API origin without trailing slashes, or an
 * empty string when relative same-origin paths should be used (Vite dev proxy
 * or unified single-container deployments).
 */
export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL
  if (typeof raw !== 'string') return ''
  return raw.trim().replace(/\/+$/, '')
}

/**
 * Resolves a backend API path against `VITE_API_BASE_URL` when configured,
 * preserving relative `/api/...` URLs when unset or empty.
 */
export function resolveApiUrl(path: string): string {
  if (HAS_URL_SCHEME_RE.test(path) || path.startsWith('//')) {
    return path
  }
  const base = getApiBaseUrl()
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return base ? `${base}${normalizedPath}` : normalizedPath
}

/**
 * Resolves an API path to a fully qualified URL with scheme + host, suitable
 * for Cornerstone3D `wadouri:` imageIds across both split-origin CDN and
 * same-origin deployments.
 */
export function resolveAbsoluteApiUrl(path: string): string {
  const resolved = resolveApiUrl(path)
  if (HAS_URL_SCHEME_RE.test(resolved)) {
    return resolved
  }
  if (typeof window !== 'undefined' && window.location?.origin) {
    return new URL(resolved, window.location.origin).toString()
  }
  return resolved
}

async function safeApiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken()
  const headers = new Headers(init?.headers)
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(resolveApiUrl(path), {
    ...init,
    headers,
    credentials: init?.credentials ?? 'include',
  })
  const raw = await res.text()

  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new ApiError(raw.trim() || `Server returned HTTP ${res.status}`, res.status)
  }

  if (!res.ok) {
    const errObj = parsed as { detail?: string; message?: string }
    throw new ApiError(errObj.detail || errObj.message || `HTTP ${res.status} error`, res.status)
  }

  return parsed as T
}

export async function loginApi(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(resolveApiUrl('/api/v1/auth/login'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
    credentials: 'include',
  })

  const raw = await res.text()
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new ApiError(raw.trim() || `Login failed with HTTP ${res.status}`, res.status)
  }

  if (!res.ok) {
    const errObj = parsed as { detail?: string; message?: string }
    throw new ApiError(errObj.detail || errObj.message || 'Invalid username or password', res.status)
  }

  const loginResp = parsed as LoginResponse
  setAuthToken(loginResp.access_token)
  return loginResp
}

export async function fetchCurrentUser(): Promise<User> {
  return safeApiRequest<User>('/api/v1/auth/me')
}

export async function logoutApi(): Promise<void> {
  try {
    await safeApiRequest<{ message: string }>('/api/v1/auth/logout', {
      method: 'POST',
    })
  } finally {
    setAuthToken(null)
  }
}

export function appendAuthTokenToUrl(urlStr: string): string {
  const token = getAuthToken()
  if (!token) return urlStr
  if (urlStr.includes('token=')) return urlStr
  const separator = urlStr.includes('?') ? '&' : '?'
  return `${urlStr}${separator}token=${encodeURIComponent(token)}`
}

export async function fetchReferenceSamples(): Promise<SampleCase[]> {
  const data = await safeApiRequest<{ samples: SampleCase[] }>('/api/v1/dashboard/samples')
  return data.samples
}

export async function fetchWorklist(): Promise<WorklistEntry[]> {
  const data = await safeApiRequest<{ worklist: WorklistEntry[] }>('/api/v1/dashboard/worklist')
  return data.worklist
}

export async function analyzeSampleCase(
  sampleId: string,
  pathologyHeatmap: string
): Promise<StudyAnalysisResponse> {
  const formData = new FormData()
  formData.append('sample_id', sampleId)
  formData.append('pathology_heatmap', pathologyHeatmap)
  return safeApiRequest<StudyAnalysisResponse>('/api/v1/dashboard/analyze', {
    method: 'POST',
    body: formData,
  })
}

export async function analyzeUploadedStudy(
  file: File,
  pathologyHeatmap: string
): Promise<StudyAnalysisResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('pathology_heatmap', pathologyHeatmap)
  return safeApiRequest<StudyAnalysisResponse>('/api/v1/dashboard/analyze', {
    method: 'POST',
    body: formData,
  })
}

export async function reanalyzeStoredStudy(
  studyUid: string,
  pathologyHeatmap: string
): Promise<StudyAnalysisResponse> {
  const formData = new FormData()
  formData.append('study_uid', studyUid)
  formData.append('pathology_heatmap', pathologyHeatmap)
  return safeApiRequest<StudyAnalysisResponse>('/api/v1/dashboard/analyze', {
    method: 'POST',
    body: formData,
  })
}

export async function shredStudyKey(studyUid: string): Promise<ShredResponse> {
  return safeApiRequest<ShredResponse>(`/api/v1/dashboard/shred/${encodeURIComponent(studyUid)}`, {
    method: 'POST',
  })
}

export function getDicomDownloadUrl(studyUid: string, download = false): string {
  const base = resolveApiUrl(`/api/v1/dashboard/studies/${encodeURIComponent(studyUid)}/dicom`)
  const url = new URL(base, typeof window !== 'undefined' && window.location?.origin ? window.location.origin : 'http://localhost')
  if (download) {
    url.searchParams.set('download', 'true')
  }
  const token = getAuthToken()
  if (token) {
    url.searchParams.set('token', token)
  }
  if (!HAS_URL_SCHEME_RE.test(base)) {
    return `${url.pathname}${url.search}`
  }
  return url.toString()
}

export async function sendScanChatMessage(
  request: ScanChatRequest
): Promise<ScanChatResponse> {
  return safeApiRequest<ScanChatResponse>('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })
}


