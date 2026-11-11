import { useEffect } from 'react'
import { ShieldCheck } from 'lucide-react'
import { Toaster } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { WorklistRail } from '@/components/sidebar/WorklistRail'
import { ViewerTabs } from '@/components/viewer/ViewerTabs'
import { CornerstoneViewport } from '@/components/viewer/CornerstoneViewport'
import { SafeHarborTable } from '@/components/audit/SafeHarborTable'
import { TriagePanel } from '@/components/diagnostics/TriagePanel'
import { EnvelopeInspector } from '@/components/security/EnvelopeInspector'
import { CryptoShredDialog } from '@/components/security/CryptoShredDialog'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function App() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const isLoading = useWorkstationStore((s) => s.isLoading)
  const loadingMessage = useWorkstationStore((s) => s.loadingMessage)
  const bootstrap = useWorkstationStore((s) => s.bootstrap)
  const setViewMode = useWorkstationStore((s) => s.setViewMode)
  const toggleInvert = useWorkstationStore((s) => s.toggleInvert)
  const triggerZoomStep = useWorkstationStore((s) => s.triggerZoomStep)
  const triggerResetViewport = useWorkstationStore((s) => s.triggerResetViewport)

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  // Global radiologist keyboard hotkeys
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null
      if (
        !useWorkstationStore.getState().activeStudy ||
        (target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName))
      ) {
        return
      }
      if (e.key === '1') setViewMode('raw')
      else if (e.key === '2') setViewMode('redacted')
      else if (e.key === '3') setViewMode('heatmap')
      else if (e.key === 'i' || e.key === 'I') toggleInvert()
      else if (e.key === '+' || e.key === '=') triggerZoomStep(1.18)
      else if (e.key === '-') triggerZoomStep(0.85)
      else if (e.key === '0' || e.key === 'r' || e.key === 'R') triggerResetViewport()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [setViewMode, toggleInvert, triggerZoomStep, triggerResetViewport])

  return (
    <>
      <div className="relative grid min-h-screen grid-cols-1 bg-bg-canvas text-[13px] text-text-primary lg:h-screen lg:grid-cols-[256px_1fr_320px] lg:grid-rows-[44px_1fr] lg:overflow-hidden">
        {/* Top Workstation Header */}
        <header className="col-span-full flex h-11 items-center justify-between border-b border-border-subtle bg-bg-panel px-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold tracking-tight text-text-primary">
              <ShieldCheck className="h-4 w-4 text-accent-verified" aria-hidden="true" />
              <span>MedShield-AI</span>
            </div>
            <span className="hidden h-3.5 w-px bg-border-subtle sm:inline-block" aria-hidden="true" />
            <span className="hidden truncate font-mono text-xs text-text-secondary sm:inline">
              {activeStudy
                ? `${activeStudy.file_name} (${activeStudy.anonymous_study_instance_uid.slice(0, 18)}...)`
                : 'No active study'}
            </span>
          </div>

          <div className="hidden items-center gap-2 sm:flex">
            <Badge variant="verified">AES-256-GCM</Badge>
            <Badge variant="neutral">PS 3.15 Annex E</Badge>
            <Badge variant="info">
              {activeStudy?.ai_diagnostics.is_real_weights
                ? 'Pretrained Clinical Weights'
                : 'Cornerstone3D PACS'}
            </Badge>
          </div>
        </header>

        {/* Center Radiograph Focal Stage first on mobile (< 1024px) */}
        <main className="order-1 flex min-w-0 flex-col overflow-hidden lg:order-2">
          <ViewerTabs />
          <CornerstoneViewport />
          <SafeHarborTable />
        </main>

        {/* Left Rail: Ingestion + AI Triage Worklist */}
        <div className="order-2 flex min-h-0 flex-col lg:order-1">
          <WorklistRail />
        </div>

        {/* Right Rail: Diagnostics, Envelope Inspection & DPDP Crypto-Shredding */}
        <aside
          aria-label="Diagnostics and cryptographic security"
          className="order-3 flex flex-col gap-3 overflow-y-auto border-t border-border-subtle bg-bg-panel p-4 lg:order-3 lg:border-t-0 lg:border-l"
        >
          <TriagePanel />
          <EnvelopeInspector />
          <CryptoShredDialog />
        </aside>
      </div>

      {/* Loading Backdrop */}
      {isLoading && (
        <div
          role="status"
          aria-live="polite"
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-2.5 bg-bg-canvas/75"
        >
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-border-subtle border-t-text-primary" />
          <p className="text-xs font-medium text-text-secondary">{loadingMessage}</p>
        </div>
      )}

      {/* Non-Blocking Toast Notifications */}
      <Toaster
        theme="dark"
        position="bottom-left"
        duration={2800}
        toastOptions={{
          classNames: {
            toast: '!bg-bg-elevated !border !border-border-strong !text-text-primary !font-sans',
            description: '!text-text-secondary',
          },
        }}
      />
    </>
  )
}

export default App
