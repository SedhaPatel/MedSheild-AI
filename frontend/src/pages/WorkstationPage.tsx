import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/layout/PageHeader'
import { StudyPicker } from '@/components/layout/StudyPicker'
import { ViewerTabs } from '@/components/viewer/ViewerTabs'
import { CornerstoneViewport } from '@/components/viewer/CornerstoneViewport'
import { TriagePanel } from '@/components/diagnostics/TriagePanel'
import { PriorityLabel } from '@/components/study/PriorityLabel'
import { selectIsActiveStudyShredded, useWorkstationStore } from '@/stores/useWorkstationStore'

const SHORTCUTS: [string, string][] = [
  ['1 / 2 / 3', 'Original / de-identified / heatmap'],
  ['I', 'Invert grayscale'],
  ['+ / −', 'Zoom in / out'],
  ['R or 0', 'Reset view'],
]

export function WorkstationPage() {
  const navigate = useNavigate()
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const setChatOpen = useWorkstationStore((s) => s.setChatOpen)
  const isShredded = useWorkstationStore(selectIsActiveStudyShredded)

  const removed = activeStudy?.deidentification.tag_diff_matrix.filter((r) => r.status === 'SANITIZED').length ?? 0

  return (
    <div className="flex flex-1 flex-col lg:h-screen lg:overflow-hidden">
      <PageHeader
        title="Viewer"
        description={
          activeStudy ? (
            <span className="font-mono">{activeStudy.anonymous_study_instance_uid}</span>
          ) : (
            'No study open'
          )
        }
        actions={
          <>
            <StudyPicker />
            <Button disabled={!activeStudy || isShredded} onClick={() => setChatOpen(true)}>
              Ask about this scan
            </Button>
            <Button variant="ghost" disabled={!activeStudy} onClick={() => navigate('/security')}>
              Audit record
            </Button>
          </>
        }
      />

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px]">
        <main className="flex min-w-0 flex-col">
          <ViewerTabs />
          <CornerstoneViewport />
        </main>

        <aside
          aria-label="Findings and study details"
          className="overflow-y-auto border-t border-border-subtle bg-bg-panel lg:border-t-0 lg:border-l"
        >
          <TriagePanel />

          {activeStudy && (
            <section className="border-t border-border-subtle px-4 py-3 text-[13px]">
              <h2 className="mb-1.5 font-semibold text-text-primary">Study</h2>
              <dl className="space-y-1.5">
                <div className="flex justify-between gap-3">
                  <dt className="text-text-muted">Priority</dt>
                  <dd><PriorityLabel urgency={activeStudy.ai_diagnostics.overall_triage_urgency} erased={isShredded} /></dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-text-muted">File</dt>
                  <dd className="truncate" title={activeStudy.file_name}>{activeStudy.file_name}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-text-muted">Identifiers</dt>
                  <dd>{removed} of {activeStudy.deidentification.tag_diff_matrix.length} removed</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-text-muted">Burned-in text</dt>
                  <dd>{activeStudy.deidentification.burned_in_text_redacted ? 'Blacked out' : 'None detected'}</dd>
                </div>
              </dl>
              <Link to="/security" className="mt-2 inline-block text-accent-brand hover:underline">
                View full audit record
              </Link>
            </section>
          )}

          <section className="border-t border-border-subtle px-4 py-3 text-[13px]">
            <h2 className="mb-1.5 font-semibold text-text-primary">Keyboard</h2>
            <dl className="space-y-1">
              {SHORTCUTS.map(([keys, action]) => (
                <div key={keys} className="flex justify-between gap-3">
                  <dt><kbd className="font-mono text-xs text-text-secondary">{keys}</kbd></dt>
                  <dd className="text-right text-text-muted">{action}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 text-xs text-text-muted">
              In the de-identified view: left-drag adjusts window/level, right-drag zooms, middle-drag pans.
            </p>
          </section>
        </aside>
      </div>
    </div>
  )
}
