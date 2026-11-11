import { useEffect, useRef, useState } from 'react'
import { Enums, RenderingEngine, type Types } from '@cornerstonejs/core'
import { ToolGroupManager } from '@cornerstonejs/tools'
import { AlertTriangle, ImageIcon } from 'lucide-react'
import {
  WORKSTATION_RENDERING_ENGINE_ID,
  WORKSTATION_TOOL_GROUP_ID,
  WORKSTATION_VIEWPORT_ID,
  ensureCornerstoneReady,
  setPrimaryMouseTool,
} from '@/lib/initCornerstone'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'
import { ViewportToolbar } from '@/components/viewer/ViewportToolbar'

export function CornerstoneViewport() {
  const csElementRef = useRef<HTMLDivElement | null>(null)
  const engineRef = useRef<RenderingEngine | null>(null)

  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const worklist = useWorkstationStore((s) => s.worklist)
  const viewMode = useWorkstationStore((s) => s.viewMode)
  const activeTool = useWorkstationStore((s) => s.activeTool)
  const heatmapOpacity = useWorkstationStore((s) => s.heatmapOpacity)
  const isInverted = useWorkstationStore((s) => s.isInverted)
  const resetSignal = useWorkstationStore((s) => s.resetSignal)
  const zoomDeltaSignal = useWorkstationStore((s) => s.zoomDeltaSignal)

  const [dicomStatus, setDicomStatus] = useState<'idle' | 'loading' | 'ready' | 'shredded' | 'fallback'>('idle')
  const [rasterZoom, setRasterZoom] = useState(1)

  const activeUid = activeStudy?.anonymous_study_instance_uid ?? null
  const isStudyShredded = Boolean(
    activeUid && worklist.find((item) => item.anonymous_study_instance_uid === activeUid)?.is_shredded
  )

  // Initialize Cornerstone3D RenderingEngine on the DICOM element
  useEffect(() => {
    let disposed = false

    async function mountCornerstone() {
      if (!csElementRef.current) return
      await ensureCornerstoneReady()
      if (disposed || !csElementRef.current) return

      const existing = engineRef.current
      if (existing) {
        try {
          existing.destroy()
        } catch {
          // Ignore teardown noise
        }
      }

      const engine = new RenderingEngine(WORKSTATION_RENDERING_ENGINE_ID)
      engineRef.current = engine

      engine.enableElement({
        viewportId: WORKSTATION_VIEWPORT_ID,
        type: Enums.ViewportType.STACK,
        element: csElementRef.current,
        defaultOptions: {
          background: [0.012, 0.016, 0.024] as Types.Point3,
        },
      })

      const toolGroup = ToolGroupManager.getToolGroup(WORKSTATION_TOOL_GROUP_ID)
      toolGroup?.addViewport(WORKSTATION_VIEWPORT_ID, WORKSTATION_RENDERING_ENGINE_ID)
      setPrimaryMouseTool(useWorkstationStore.getState().activeTool)
    }

    void mountCornerstone()

    const observer = new ResizeObserver(() => {
      if (engineRef.current) {
        try {
          engineRef.current.resize(true, false)
        } catch {
          // Viewport may not yet have actors loaded
        }
      }
    })
    if (csElementRef.current) observer.observe(csElementRef.current)

    return () => {
      disposed = true
      observer.disconnect()
      const toolGroup = ToolGroupManager.getToolGroup(WORKSTATION_TOOL_GROUP_ID)
      toolGroup?.removeViewports(WORKSTATION_RENDERING_ENGINE_ID, WORKSTATION_VIEWPORT_ID)
      if (engineRef.current) {
        try {
          engineRef.current.disableElement(WORKSTATION_VIEWPORT_ID)
          engineRef.current.destroy()
        } catch {
          // Safe cleanup on StrictMode unmount
        }
        engineRef.current = null
      }
    }
  }, [])

  // Load sanitized Part 10 DICOM stream via wadouri whenever study changes or view returns to redacted
  useEffect(() => {
    let cancelled = false

    async function loadStudyIntoCornerstone() {
      if (!activeStudy || viewMode !== 'redacted') return
      if (isStudyShredded) {
        setDicomStatus('shredded')
        return
      }

      setDicomStatus('loading')
      await ensureCornerstoneReady()
      if (cancelled || !engineRef.current) return

      const viewport = engineRef.current.getViewport(WORKSTATION_VIEWPORT_ID) as Types.IStackViewport | undefined
      if (!viewport) return

      const imageId = `wadouri:${window.location.origin}${activeStudy.dicom_url}`
      try {
        await viewport.setStack([imageId], 0)
        if (cancelled) return
        if (viewport.getCornerstoneImage()) {
          viewport.resetCamera()
          viewport.setProperties({ invert: useWorkstationStore.getState().isInverted })
          viewport.render()
          setDicomStatus('ready')
        } else {
          setDicomStatus('fallback')
        }
      } catch {
        if (!cancelled) {
          setDicomStatus(isStudyShredded ? 'shredded' : 'fallback')
        }
      }
    }

    void loadStudyIntoCornerstone()
    return () => {
      cancelled = true
    }
  }, [activeStudy, viewMode, isStudyShredded])

  // Sync active Cornerstone mouse tool
  useEffect(() => {
    setPrimaryMouseTool(activeTool)
  }, [activeTool])

  // Sync polarity invert across Cornerstone & raster views
  useEffect(() => {
    if (viewMode !== 'redacted' || !engineRef.current || dicomStatus !== 'ready') return
    const viewport = engineRef.current.getViewport(WORKSTATION_VIEWPORT_ID) as Types.IStackViewport | undefined
    if (!viewport || !viewport.getCornerstoneImage()) return
    try {
      viewport.setProperties({ invert: isInverted })
      viewport.render()
    } catch {
      // Ignore if viewport unloaded concurrently
    }
  }, [isInverted, viewMode, dicomStatus])

  // Handle reset trigger
  useEffect(() => {
    setRasterZoom(1)
    if (!engineRef.current || dicomStatus !== 'ready') return
    const viewport = engineRef.current.getViewport(WORKSTATION_VIEWPORT_ID) as Types.IStackViewport | undefined
    if (!viewport || !viewport.getCornerstoneImage()) return
    try {
      viewport.resetProperties()
      viewport.resetCamera()
      viewport.render()
    } catch {
      // Ignore if viewport unloaded concurrently
    }
  }, [resetSignal, dicomStatus])

  // Handle incremental zoom steps from toolbar/hotkeys
  useEffect(() => {
    if (zoomDeltaSignal.seq === 0) return
    if (viewMode === 'redacted' && engineRef.current && dicomStatus === 'ready') {
      const viewport = engineRef.current.getViewport(WORKSTATION_VIEWPORT_ID) as Types.IStackViewport | undefined
      if (!viewport || !viewport.getCornerstoneImage()) return
      try {
        const currentZoom = viewport.getZoom()
        viewport.setZoom(Math.max(0.4, Math.min(5, currentZoom * zoomDeltaSignal.factor)))
        viewport.render()
      } catch {
        // Ignore if viewport unloaded concurrently
      }
    } else {
      setRasterZoom((z) => Math.max(0.5, Math.min(4, z * zoomDeltaSignal.factor)))
    }
  }, [zoomDeltaSignal, viewMode, dicomStatus])

  const showCornerstoneCanvas = Boolean(activeStudy && viewMode === 'redacted' && dicomStatus !== 'shredded' && dicomStatus !== 'fallback')

  return (
    <div className="lightbox-vignette relative flex min-h-[420px] flex-1 items-center justify-center overflow-hidden bg-bg-lightbox select-none">
      {/* Empty placeholder */}
      {!activeStudy && (
        <div className="z-10 flex max-w-xs flex-col items-center gap-2.5 px-6 text-center text-text-muted">
          <ImageIcon className="h-8 w-8 stroke-1 opacity-60" aria-hidden="true" />
          <p className="text-xs leading-relaxed">
            Select a reference clinical case or drop a DICOM chest study to open the reading viewport.
          </p>
        </div>
      )}

      {/* Persistent Cornerstone3D WebGL/Stack Element */}
      <div
        ref={csElementRef}
        data-testid="cornerstone-viewport"
        className={cn(
          'h-full w-full',
          showCornerstoneCanvas ? 'opacity-100' : 'pointer-events-none invisible absolute inset-0 opacity-0'
        )}
      />

      {/* Destroyed study state (DPDP Sec. 12 proof) */}
      {activeStudy && isStudyShredded && viewMode === 'redacted' && (
        <div className="z-10 flex max-w-sm flex-col items-center gap-2 rounded-[var(--panel-radius)] border border-accent-critical/30 bg-bg-panel px-5 py-4 text-center">
          <AlertTriangle className="h-5 w-5 text-accent-critical" aria-hidden="true" />
          <p className="text-xs font-semibold text-accent-critical">
            Ciphertext Permanently Unrecoverable (HTTP 410)
          </p>
          <p className="text-[11px] leading-relaxed text-text-secondary">
            Study Master KEK was destroyed under DPDP Act Sec. 12. Decryption of sanitized DICOM bytes is mathematically impossible.
          </p>
        </div>
      )}

      {/* Raster Raw / Fallback Redacted / Synchronized Dual-Layer Grad-CAM Stage */}
      {activeStudy &&
        (viewMode === 'raw' ||
          viewMode === 'heatmap' ||
          (viewMode === 'redacted' && dicomStatus === 'fallback')) && (
          <div className="relative z-1 flex h-full w-full items-center justify-center p-4">
            <div
              className="relative inline-flex max-h-full max-w-full items-center justify-center rounded-[var(--viewport-radius)] ring-1 ring-border-film transition-transform duration-100"
              style={{ transform: `scale(${rasterZoom})` }}
            >
              <img
                src={
                  viewMode === 'raw'
                    ? activeStudy.images.raw_image_url
                    : activeStudy.images.redacted_image_url
                }
                alt={
                  viewMode === 'raw'
                    ? 'Raw radiograph with pre-sanitization PHI'
                    : 'De-identified thoracic radiograph'
                }
                className={cn(
                  'block max-h-[calc(100vh-340px)] max-w-full rounded-[var(--viewport-radius)] object-contain',
                  isInverted && 'invert'
                )}
              />

              {viewMode === 'heatmap' && (
                <img
                  src={activeStudy.images.gradcam_heatmap_url}
                  alt={`Grad-CAM localization for ${activeStudy.ai_diagnostics.active_heatmap_pathology}`}
                  className="pointer-events-none absolute inset-0 h-full w-full rounded-[var(--viewport-radius)] object-fill transition-opacity duration-100"
                  style={{ opacity: heatmapOpacity / 100 }}
                />
              )}
            </div>
          </div>
        )}

      <ViewportToolbar />
    </div>
  )
}

