import { create } from 'zustand'
import { toast } from 'sonner'
import type {
  PACSActiveTool,
  SampleCase,
  StudyAnalysisResponse,
  ViewPlaneMode,
  WorklistEntry,
} from '@/types/clinical'
import {
  analyzeSampleCase,
  analyzeUploadedStudy,
  fetchReferenceSamples,
  fetchWorklist,
  reanalyzeStoredStudy,
  shredStudyKey,
} from '@/lib/api'

interface WorkstationState {
  samples: SampleCase[]
  worklist: WorklistEntry[]
  activeStudy: StudyAnalysisResponse | null
  activeSampleId: string | null
  viewMode: ViewPlaneMode
  activeTool: PACSActiveTool
  heatmapOpacity: number
  targetPathology: string
  isInverted: boolean
  isLoading: boolean
  loadingMessage: string
  resetSignal: number
  zoomDeltaSignal: { seq: number; factor: number }

  bootstrap: () => Promise<void>
  ingestSample: (sampleId: string) => Promise<void>
  ingestFile: (file: File) => Promise<void>
  selectWorklistStudy: (studyUid: string) => Promise<void>
  changePathologyHeatmap: (pathology: string) => Promise<void>
  cryptoShredActiveStudy: () => Promise<void>

  setViewMode: (mode: ViewPlaneMode) => void
  setActiveTool: (tool: PACSActiveTool) => void
  setHeatmapOpacity: (value: number) => void
  toggleInvert: () => void
  triggerResetViewport: () => void
  triggerZoomStep: (factor: number) => void
}

export const useWorkstationStore = create<WorkstationState>((set, get) => ({
  samples: [],
  worklist: [],
  activeStudy: null,
  activeSampleId: null,
  viewMode: 'redacted',
  activeTool: 'WindowLevel',
  heatmapOpacity: 80,
  targetPathology: 'Pneumonia',
  isInverted: false,
  isLoading: false,
  loadingMessage: '',
  resetSignal: 0,
  zoomDeltaSignal: { seq: 0, factor: 1 },

  bootstrap: async () => {
    try {
      const [samples, worklist] = await Promise.all([
        fetchReferenceSamples(),
        fetchWorklist().catch(() => []),
      ])
      set({ samples, worklist })
    } catch (err) {
      toast.error('Failed to connect to MedShield API', {
        description: err instanceof Error ? err.message : 'Check uvicorn server status',
      })
    }
  },

  ingestSample: async (sampleId) => {
    const { targetPathology } = get()
    set({ isLoading: true, loadingMessage: 'Sanitizing DICOM tags, encrypting & running inference' })
    try {
      const data = await analyzeSampleCase(sampleId, targetPathology)
      set((s) => ({
        activeStudy: data,
        activeSampleId: sampleId,
        worklist: data.worklist ?? s.worklist,
        targetPathology: data.ai_diagnostics.active_heatmap_pathology,
        isInverted: false,
        resetSignal: s.resetSignal + 1,
      }))
      toast.success('Study ingested & sealed', {
        description: `${data.file_name} • H=${data.security.shannon_entropy_bits_per_byte} bits/byte`,
      })
    } catch (err) {
      toast.error('Ingestion failed', {
        description: err instanceof Error ? err.message : 'Unexpected server response',
      })
    } finally {
      set({ isLoading: false, loadingMessage: '' })
    }
  },

  ingestFile: async (file) => {
    const valid = ['.dcm', '.png', '.jpg', '.jpeg'].some((ext) =>
      file.name.toLowerCase().endsWith(ext)
    )
    if (!valid) {
      toast.warning('Unsupported scan format', {
        description: 'Upload a DICOM (.dcm) or thoracic scan image (.png, .jpg).',
      })
      return
    }

    const { targetPathology } = get()
    set({ isLoading: true, loadingMessage: `Sanitizing & encrypting ${file.name}` })
    try {
      const data = await analyzeUploadedStudy(file, targetPathology)
      set((s) => ({
        activeStudy: data,
        activeSampleId: null,
        worklist: data.worklist ?? s.worklist,
        targetPathology: data.ai_diagnostics.active_heatmap_pathology,
        isInverted: false,
        resetSignal: s.resetSignal + 1,
      }))
      toast.success('Uploaded study sealed', {
        description: `${data.file_name} • AES-256-GCM (${data.security.shannon_entropy_bits_per_byte} bits/byte)`,
      })
    } catch (err) {
      toast.error('Upload error', {
        description: err instanceof Error ? err.message : 'Upload processing failed',
      })
    } finally {
      set({ isLoading: false, loadingMessage: '' })
    }
  },

  selectWorklistStudy: async (studyUid) => {
    const { targetPathology } = get()
    set({ isLoading: true, loadingMessage: 'Decrypting study envelope in RAM' })
    try {
      const data = await reanalyzeStoredStudy(studyUid, targetPathology)
      set((s) => ({
        activeStudy: data,
        activeSampleId: null,
        worklist: data.worklist ?? s.worklist,
        targetPathology: data.ai_diagnostics.active_heatmap_pathology,
        isInverted: false,
        resetSignal: s.resetSignal + 1,
      }))
    } catch (err) {
      const worklist = await fetchWorklist().catch(() => get().worklist)
      set({ worklist })
      toast.error('Unable to decrypt study', {
        description: err instanceof Error ? err.message : 'Study key may have been crypto-shredded',
      })
    } finally {
      set({ isLoading: false, loadingMessage: '' })
    }
  },

  changePathologyHeatmap: async (pathology) => {
    const { activeStudy } = get()
    set({ targetPathology: pathology })
    if (!activeStudy) return

    set({ isLoading: true, loadingMessage: `Computing Grad-CAM saliency for ${pathology}` })
    try {
      const data = await reanalyzeStoredStudy(activeStudy.anonymous_study_instance_uid, pathology)
      set((s) => ({
        activeStudy: data,
        viewMode: 'heatmap',
        worklist: data.worklist ?? s.worklist,
        targetPathology: data.ai_diagnostics.active_heatmap_pathology,
      }))
      toast.info('Grad-CAM localization updated', {
        description: `Target pathology: ${pathology}`,
      })
    } catch (err) {
      toast.error('Heatmap computation failed', {
        description: err instanceof Error ? err.message : 'Could not update heatmap',
      })
    } finally {
      set({ isLoading: false, loadingMessage: '' })
    }
  },

  cryptoShredActiveStudy: async () => {
    const { activeStudy } = get()
    if (!activeStudy) return
    const uid = activeStudy.anonymous_study_instance_uid

    set({ isLoading: true, loadingMessage: 'Executing DPDP Sec. 12 key destruction' })
    try {
      const res = await shredStudyKey(uid)
      set((s) => ({ worklist: res.worklist ?? s.worklist }))
      toast.success('Cryptographic erasure verified', {
        description: `${res.revoked_kek_id.slice(-24)} overwritten; ciphertext permanently unrecoverable.`,
      })
    } catch (err) {
      toast.error('Crypto-shredding failed', {
        description: err instanceof Error ? err.message : 'Failed to shred key',
      })
    } finally {
      set({ isLoading: false, loadingMessage: '' })
    }
  },

  setViewMode: (viewMode) => set({ viewMode }),
  setActiveTool: (activeTool) => set({ activeTool }),
  setHeatmapOpacity: (heatmapOpacity) => set({ heatmapOpacity }),
  toggleInvert: () => set((s) => ({ isInverted: !s.isInverted })),
  triggerResetViewport: () =>
    set((s) => ({ isInverted: false, resetSignal: s.resetSignal + 1 })),
  triggerZoomStep: (factor) =>
    set((s) => ({ zoomDeltaSignal: { seq: s.zoomDeltaSignal.seq + 1, factor } })),
}))

