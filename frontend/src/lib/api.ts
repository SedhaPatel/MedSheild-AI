import type {
  SampleCase,
  ScanChatRequest,
  ScanChatResponse,
  ShredResponse,
  StudyAnalysisResponse,
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

async function safeApiRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
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
  const base = `/api/v1/dashboard/studies/${encodeURIComponent(studyUid)}/dicom`
  return download ? `${base}?download=true` : base
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


