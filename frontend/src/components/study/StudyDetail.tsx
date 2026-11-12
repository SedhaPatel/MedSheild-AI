import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { TriagePanel } from '@/components/diagnostics/TriagePanel'
import { PriorityLabel } from '@/components/study/PriorityLabel'
import { PATHOLOGY_GUIDE } from '@/lib/pathologyGuide'
import { isPositive, rankPredictions } from '@/lib/scores'
import { selectIsActiveStudyShredded, useWorkstationStore } from '@/stores/useWorkstationStore'

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[132px_1fr] gap-2 py-1.5">
      <dt className="text-text-muted">{label}</dt>
      <dd className="min-w-0 text-text-primary">{children}</dd>
    </div>
  )
}

/** Result summary for the open study, shown beside the study list. */
export function StudyDetail() {
  const navigate = useNavigate()
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const isShredded = useWorkstationStore(selectIsActiveStudyShredded)
  const showHeatmap = useWorkstationStore((s) => s.previewHeatmap)
  const setShowHeatmap = useWorkstationStore((s) => s.setPreviewHeatmap)
  const setChatOpen = useWorkstationStore((s) => s.setChatOpen)

  if (!activeStudy) {
    return (
      <div className="px-5 py-8 text-[13px] text-text-muted">
        Select a study to see its result, or upload one.
      </div>
    )
  }

  if (isShredded) {
    return (
      <div className="space-y-1 px-5 py-8 text-[13px]">
        <p className="font-medium text-text-primary">{activeStudy.file_name} was erased.</p>
        <p className="text-text-muted">
          Its encryption key was destroyed (crypto-shredding), so the image and results can no longer be decrypted.
        </p>
      </div>
    )
  }

  const deid = activeStudy.deidentification
  const removed = deid.tag_diff_matrix.filter((r) => r.status === 'SANITIZED').length
  const ranked = rankPredictions(activeStudy.ai_diagnostics.predictions)
  const top = ranked[0]
  const positives = ranked.filter(isPositive)
  const guide = top ? PATHOLOGY_GUIDE[top.pathology] : undefined

  return (
    <div className="divide-y divide-border-subtle">
      {/* Identity */}
      <div className="space-y-1 px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <h2 className="min-w-0 truncate text-[15px] font-semibold text-text-primary" title={activeStudy.file_name}>
            {activeStudy.file_name}
          </h2>
          <PriorityLabel urgency={activeStudy.ai_diagnostics.overall_triage_urgency} />
        </div>
        <p className="truncate font-mono text-xs text-text-muted" title={activeStudy.anonymous_study_instance_uid}>
          {activeStudy.anonymous_study_instance_uid}
        </p>
        <p className="pt-1 text-[13px] text-text-secondary">
          {positives.length === 0
            ? 'No finding above the model threshold.'
            : `Above threshold: ${positives.map((p) => p.pathology).join(', ')}.`}
        </p>
      </div>

      {/* Image */}
      <div className="px-4 py-3">
        <div className="relative flex aspect-square items-center justify-center overflow-hidden bg-bg-lightbox">
          <img
            src={activeStudy.images.redacted_image_url}
            alt="De-identified radiograph"
            className="max-h-full max-w-full object-contain"
          />
          {showHeatmap && (
            <img
              src={activeStudy.images.gradcam_heatmap_url}
              alt={`Heatmap for ${activeStudy.ai_diagnostics.active_heatmap_pathology}`}
              className="pointer-events-none absolute inset-0 h-full w-full object-contain opacity-80"
            />
          )}
        </div>
        <label className="mt-2 flex cursor-pointer items-center gap-2 text-xs text-text-secondary">
          <input
            type="checkbox"
            checked={showHeatmap}
            onChange={(e) => setShowHeatmap(e.target.checked)}
            className="h-3.5 w-3.5 accent-[var(--accent-brand)]"
          />
          Show heatmap for {activeStudy.ai_diagnostics.active_heatmap_pathology}
        </label>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 px-4 py-3">
        <Button variant="primary" onClick={() => navigate('/workstation')}>Open in viewer</Button>
        <Button onClick={() => setChatOpen(true)}>Ask about this scan</Button>
        <Button variant="ghost" onClick={() => navigate('/security')}>Audit record</Button>
      </div>

      <TriagePanel />

      {/* Privacy & storage summary */}
      <dl className="px-4 py-2 text-[13px]">
        <Row label="Identifiers">
          {removed} of {deid.tag_diff_matrix.length} tracked tags removed or pseudonymized
        </Row>
        <Row label="Burned-in text">{deid.burned_in_text_redacted ? 'Found and blacked out' : 'None detected'}</Row>
        <Row label="Storage">
          AES-256-GCM, {activeStudy.security.storage_file_size_bytes.toLocaleString()} bytes
        </Row>
        <Row label="Model">{activeStudy.ai_diagnostics.model_name}</Row>
      </dl>

      {guide && top && (
        <details className="group px-4 py-3 text-[13px]">
          <summary className="cursor-pointer text-text-secondary select-none hover:text-text-primary">
            About {top.pathology.toLowerCase()} (reference)
          </summary>
          <dl className="mt-2 space-y-2 text-text-secondary">
            <div>
              <dt className="text-xs text-text-muted">Typical appearance</dt>
              <dd>{guide.looksLike}</dd>
            </div>
            <div>
              <dt className="text-xs text-text-muted">Commonly confused with</dt>
              <dd>{guide.lookalikes}</dd>
            </div>
          </dl>
          <p className="mt-2 text-xs text-text-muted">General radiology reference, not a description of this image.</p>
        </details>
      )}
    </div>
  )
}
