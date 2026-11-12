import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AppShell } from '@/components/layout/AppShell'
import { OverviewPage } from '@/pages/OverviewPage'
import { WorklistPage } from '@/pages/WorklistPage'
import { WorkstationPage } from '@/pages/WorkstationPage'
import { SecurityAuditPage } from '@/pages/SecurityAuditPage'
import { ScanChatDrawer } from '@/components/diagnostics/ScanChatDrawer'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function App() {
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
      if (useWorkstationStore.getState().chatOpen) {
        return
      }
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
      <TooltipProvider delayDuration={200}>
        <BrowserRouter>
          <AppShell>
            <Routes>
              <Route path="/" element={<OverviewPage />} />
              <Route path="/worklist" element={<WorklistPage />} />
              <Route path="/workstation" element={<WorkstationPage />} />
              <Route path="/security" element={<SecurityAuditPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AppShell>
          <ScanChatDrawer />
        </BrowserRouter>
      </TooltipProvider>

      {/* Daylight Frosted Loading Overlay */}
      {isLoading && (
        <div
          role="status"
          aria-live="polite"
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-3 bg-bg-backdrop backdrop-blur-xs"
        >
          <div className="h-7 w-7 animate-spin rounded-full border-2 border-border-strong border-t-accent-brand" />
          <p className="rounded-[var(--control-radius)] border border-border-subtle bg-bg-panel px-3.5 py-1.5 text-xs font-medium text-text-primary">
            {loadingMessage}
          </p>
        </div>
      )}

      {/* Daylight Toast Notifications */}
      <Toaster
        theme="light"
        position="bottom-left"
        duration={2800}
        toastOptions={{
          classNames: {
            toast: '!bg-bg-panel !border !border-border-strong !text-text-primary !font-sans',
            description: '!text-text-secondary',
          },
        }}
      />
    </>
  )
}

export default App
