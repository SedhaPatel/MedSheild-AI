import { create } from 'zustand'
import { toast } from 'sonner'
import type {
  PACSActiveTool,
  SampleCase,
  ScanChatMessage,
  ScanChatTurn,
  StudyAnalysisResponse,
  ViewPlaneMode,
  WorklistEntry,
} from '@/types/clinical'
import {
  ApiError,
  analyzeSampleCase,
  analyzeUploadedStudy,
  fetchReferenceSamples,
  fetchWorklist,
  reanalyzeStoredStudy,
  sendScanChatMessage,
  shredStudyKey,
} from '@/lib/api'

export interface WorkstationState {
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
  chatOpen: boolean
  isChatSending: boolean
  chatMessagesByStudy: Record<string, ScanChatMessage[]>
  previewHeatmap: boolean

  bootstrap: () => Promise<void>
  ingestSample: (sampleId: string) => Promise<void>
  ingestFile: (file: File) => Promise<void>
  selectWorklistStudy: (studyUid: string) => Promise<void>
  changePathologyHeatmap: (pathology: string) => Promise<void>
  cryptoShredActiveStudy: () => Promise<void>
  askScanQuestion: (question: string) => Promise<void>
  retryScanQuestion: (noticeId: string) => Promise<void>
  clearScanChat: () => void

  setChatOpen: (open: boolean) => void
  setPreviewHeatmap: (value: boolean | ((prev: boolean) => boolean)) => void
  setViewMode: (mode: ViewPlaneMode) => void
  setActiveTool: (tool: PACSActiveTool) => void
  setHeatmapOpacity: (value: number) => void
  toggleInvert: () => void
  triggerResetViewport: () => void
  triggerZoomStep: (factor: number) => void
}

export const selectIsActiveStudyShredded = (s: WorkstationState): boolean =>
  Boolean(
    s.activeStudy &&
      s.worklist.some(
        (w) =>
          w.anonymous_study_instance_uid ===
            s.activeStudy?.anonymous_study_instance_uid && w.is_shredded
      )
  )

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
  chatOpen: false,
  isChatSending: false,
  chatMessagesByStudy: {},
  previewHeatmap: false,

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
        previewHeatmap: false,
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
        previewHeatmap: false,
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
      set((s) => {
        const existingChat = s.chatMessagesByStudy[uid] ?? []
        const erasureNotice: ScanChatMessage = {
          id: `sys-${Date.now()}`,
          role: 'system',
          content:
            'Study cryptographic key has been destroyed under DPDP Act Sec. 12 (Right to Erasure). Plaintext image and AI chat context are permanently unrecoverable.',
          timestamp: Date.now(),
          isError: true,
        }

        return {
          worklist: res.worklist ?? s.worklist,
          chatMessagesByStudy: {
            ...s.chatMessagesByStudy,
            [uid]: [...existingChat, erasureNotice],
          },
        }
      })
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

  askScanQuestion: async (question: string) => {
    const {
      activeStudy,
      targetPathology,
      viewMode,
      previewHeatmap,
      chatMessagesByStudy,
      isChatSending,
    } = get()
    const trimmed = question.trim()
    if (!activeStudy || !trimmed || isChatSending) return

    const scanId = activeStudy.anonymous_study_instance_uid
    const userMessage: ScanChatMessage = {
      id: `user-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    }

    const existingMessages = chatMessagesByStudy[scanId] ?? []
    set((s) => ({
      isChatSending: true,
      chatMessagesByStudy: {
        ...s.chatMessagesByStudy,
        [scanId]: [...existingMessages, userMessage],
      },
    }))

    const conversationHistory: ScanChatTurn[] = existingMessages
      .filter((m) => m.role !== 'system' && !m.isError)
      .map((m) => ({
        role: m.role as 'user' | 'assistant',
        // Server caps each history turn at 8000 chars; keep the most recent context only
        content: m.content.length > 6000 ? `${m.content.slice(0, 6000)}…` : m.content,
      }))
      .slice(-6)

    const includeHeatmap =
      viewMode === 'heatmap' ||
      previewHeatmap ||
      trimmed.toLowerCase().includes('heatmap')
    const pathology =
      targetPathology || activeStudy.ai_diagnostics.active_heatmap_pathology

    try {
      const resp = await sendScanChatMessage({
        scan_id: scanId,
        user_message: trimmed,
        target_pathology: pathology,
        include_heatmap_overlay: includeHeatmap,
        conversation_history: conversationHistory,
      })

      const assistantMessage: ScanChatMessage = {
        id: `asst-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        role: 'assistant',
        content: resp.answer,
        provider_used: resp.provider_used,
        grounded_findings: resp.grounded_findings,
        suggested_questions: resp.suggested_questions ?? [],
        pii_redacted: resp.pii_redacted_from_prompt,
        timestamp: Date.now(),
      }

      set((s) => ({
        chatMessagesByStudy: {
          ...s.chatMessagesByStudy,
          [scanId]: [...(s.chatMessagesByStudy[scanId] ?? []), assistantMessage],
        },
      }))
    } catch (err) {
      if (err instanceof ApiError && err.status === 410) {
        const systemNotice: ScanChatMessage = {
          id: `sys-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          role: 'system',
          content:
            'This study was erased (its encryption key was destroyed under DPDP Act Sec. 12), so it can no longer be queried.',
          timestamp: Date.now(),
          isError: true,
          title: 'Study erased',
        }
        set((s) => ({
          chatMessagesByStudy: {
            ...s.chatMessagesByStudy,
            [scanId]: [...(s.chatMessagesByStudy[scanId] ?? []), systemNotice],
          },
        }))
        fetchWorklist()
          .then((worklist) => set({ worklist }))
          .catch(() => undefined)
        toast.error('Study erased', {
          description: 'This study can no longer be queried.',
        })
      } else {
        const errorNotice: ScanChatMessage = {
          id: `err-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          role: 'system',
          content:
            err instanceof Error ? err.message : 'Chat assistant query failed',
          timestamp: Date.now(),
          isError: true,
          title: 'Request failed',
          retryQuestion: trimmed,
        }
        set((s) => ({
          chatMessagesByStudy: {
            ...s.chatMessagesByStudy,
            [scanId]: [...(s.chatMessagesByStudy[scanId] ?? []), errorNotice],
          },
        }))
        toast.error('Chat request failed', {
          description: err instanceof Error ? err.message : 'Chat request failed',
        })
      }
    } finally {
      set({ isChatSending: false })
    }
  },

  retryScanQuestion: async (noticeId) => {
    const { activeStudy, chatMessagesByStudy, isChatSending } = get()
    if (!activeStudy || isChatSending) return
    const scanId = activeStudy.anonymous_study_instance_uid
    const messages = chatMessagesByStudy[scanId] ?? []
    const idx = messages.findIndex((m) => m.id === noticeId)
    const question = idx >= 0 ? messages[idx].retryQuestion : undefined
    if (!question) return
    // Drop the failed question and its error notice, then ask again
    const failedUserIdx = messages.slice(0, idx).map((m) => m.role).lastIndexOf('user')
    const kept = messages.filter((_, i) => i !== idx && i !== failedUserIdx)
    set((s) => ({ chatMessagesByStudy: { ...s.chatMessagesByStudy, [scanId]: kept } }))
    await get().askScanQuestion(question)
  },

  clearScanChat: () => {
    const { activeStudy } = get()
    if (!activeStudy) return
    const scanId = activeStudy.anonymous_study_instance_uid
    set((s) => ({ chatMessagesByStudy: { ...s.chatMessagesByStudy, [scanId]: [] } }))
  },

  setChatOpen: (chatOpen) => set({ chatOpen }),
  setPreviewHeatmap: (value) =>
    set((s) => ({
      previewHeatmap:
        typeof value === 'function' ? value(s.previewHeatmap) : value,
    })),
  setViewMode: (viewMode) => set({ viewMode }),
  setActiveTool: (activeTool) => set({ activeTool }),
  setHeatmapOpacity: (heatmapOpacity) => set({ heatmapOpacity }),
  toggleInvert: () => set((s) => ({ isInverted: !s.isInverted })),
  triggerResetViewport: () =>
    set((s) => ({ isInverted: false, resetSignal: s.resetSignal + 1 })),
  triggerZoomStep: (factor) =>
    set((s) => ({ zoomDeltaSignal: { seq: s.zoomDeltaSignal.seq + 1, factor } })),
}))


