import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'
import { IngestionDropzone } from '@/components/sidebar/IngestionDropzone'

export function WorklistRail() {
  const samples = useWorkstationStore((s) => s.samples)
  const worklist = useWorkstationStore((s) => s.worklist)
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const activeSampleId = useWorkstationStore((s) => s.activeSampleId)
  const ingestSample = useWorkstationStore((s) => s.ingestSample)
  const selectWorklistStudy = useWorkstationStore((s) => s.selectWorklistStudy)

  return (
    <nav
      aria-label="Study ingestion and AI triage worklist"
      className="flex flex-1 flex-col gap-5 overflow-y-auto border-b border-border-subtle bg-bg-panel p-4 lg:border-r lg:border-b-0"
    >
      <IngestionDropzone />

      {/* Pre-packaged Clinical Samples */}
      <div className="space-y-2">
        <div className="text-[11px] font-medium tracking-wide text-text-secondary">
          Reference Cases
        </div>
        <div className="flex flex-col gap-1.5">
          {samples.map((sample) => {
            const isSelected = activeSampleId === sample.id
            return (
              <button
                key={sample.id}
                type="button"
                onClick={() => {
                  void ingestSample(sample.id)
                }}
                className={cn(
                  'w-full cursor-pointer rounded-[var(--control-radius)] border px-3 py-2 text-left transition-colors active:scale-[0.98]',
                  isSelected
                    ? 'border-accent-info/50 bg-accent-info/10'
                    : 'border-border-subtle bg-bg-canvas hover:border-border-strong hover:bg-bg-elevated'
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-xs font-semibold text-text-primary">
                    {sample.name.replace(/^Patient \d+: /, '')}
                  </span>
                  <Badge variant="attention">Elevated</Badge>
                </div>
                <div className="mt-1 line-clamp-1 text-[11px] text-text-muted">
                  {sample.finding}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Live Session AI Triage Worklist Queue */}
      {worklist.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium tracking-wide text-text-secondary">
              Session Queue
            </span>
            <span className="font-mono text-[10px] text-text-muted tabular-nums">
              {worklist.length} active
            </span>
          </div>
          <div className="flex flex-col gap-1.5">
            {worklist.map((entry) => {
              const isCurrent =
                activeStudy?.anonymous_study_instance_uid ===
                entry.anonymous_study_instance_uid
              const urgencyVariant = entry.is_shredded
                ? 'critical'
                : entry.overall_triage_urgency === 'STAT_CRITICAL'
                  ? 'critical'
                  : entry.overall_triage_urgency === 'ELEVATED'
                    ? 'attention'
                    : 'verified'

              return (
                <button
                  key={entry.anonymous_study_instance_uid}
                  type="button"
                  onClick={() => {
                    void selectWorklistStudy(entry.anonymous_study_instance_uid)
                  }}
                  className={cn(
                    'w-full cursor-pointer rounded-[var(--control-radius)] border px-3 py-2 text-left transition-colors active:scale-[0.98]',
                    isCurrent
                      ? 'border-accent-info/50 bg-accent-info/10'
                      : 'border-border-subtle bg-bg-canvas hover:border-border-strong hover:bg-bg-elevated'
                  )}
                >
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="truncate font-mono text-[11px] font-medium text-text-primary">
                      {entry.file_name}
                    </span>
                    <Badge variant={urgencyVariant}>
                      {entry.is_shredded
                        ? 'Shredded'
                        : entry.overall_triage_urgency.replace('_', ' ')}
                    </Badge>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[10px] text-text-muted">
                    <span>
                      {entry.top_pathology} ({(entry.top_probability * 100).toFixed(0)}%)
                    </span>
                    <span className="font-mono">{entry.modality}</span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Pipeline Metadata */}
      <div className="mt-auto space-y-1.5 border-t border-border-subtle pt-3 text-[11px]">
        <div className="font-medium tracking-wide text-text-secondary">
          System Profile
        </div>
        <div className="flex items-center justify-between">
          <span className="text-text-muted">DICOM Engine</span>
          <span className="font-medium text-text-secondary">Cornerstone3D</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="shrink-0 text-text-muted">Backbone</span>
          <span className="truncate font-medium text-text-secondary">
            {activeStudy?.ai_diagnostics.model_name ?? 'DenseNet121'}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-text-muted">Weights Source</span>
          <span className="font-medium text-text-secondary">
            {activeStudy?.ai_diagnostics.is_real_weights ? 'TorchXRayVision' : 'Clinical Core'}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-text-muted">De-ID Standard</span>
          <span className="font-medium text-text-secondary">PS 3.15 Annex E</span>
        </div>
      </div>
    </nav>
  )
}

