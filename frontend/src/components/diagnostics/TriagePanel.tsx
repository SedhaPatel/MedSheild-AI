import { cn } from '@/lib/utils'
import {
  SCORE_EXPLANATION,
  SCORE_THRESHOLD,
  formatScore,
  isBorderline,
  isPositive,
  scoreVerdict,
} from '@/lib/scores'
import { useWorkstationStore } from '@/stores/useWorkstationStore'
import type { PredictionItem } from '@/types/clinical'

function tone(pred: PredictionItem) {
  if (!isPositive(pred)) return { text: 'text-text-secondary', bar: 'bg-text-muted/60' }
  if (pred.triage_urgency === 'STAT_CRITICAL') return { text: 'text-accent-critical', bar: 'bg-accent-critical' }
  return { text: 'text-accent-attention', bar: 'bg-accent-attention' }
}

/**
 * Model findings as a plain list. Clicking a finding switches the Grad-CAM heatmap to it.
 * Renders without its own card; the parent provides the container.
 */
export function TriagePanel() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const targetPathology = useWorkstationStore((s) => s.targetPathology)
  const changePathologyHeatmap = useWorkstationStore((s) => s.changePathologyHeatmap)

  return (
    <section aria-label="Model findings">
      <div className="flex items-baseline justify-between px-4 pt-3 pb-1.5">
        <h2 className="text-[13px] font-semibold text-text-primary">Findings</h2>
        {activeStudy && (
          <span className="text-xs text-text-muted tabular-nums">
            {activeStudy.ai_diagnostics.inference_latency_ms} ms
          </span>
        )}
      </div>

      {!activeStudy ? (
        <p className="px-4 pb-4 text-[13px] text-text-muted">No study open.</p>
      ) : (
        <>
          <ul className="divide-y divide-border-subtle border-y border-border-subtle">
            {activeStudy.ai_diagnostics.predictions.map((pred) => {
              const score = pred.probability
              const t = tone(pred)
              const isSelected = targetPathology === pred.pathology
              return (
                <li key={pred.pathology}>
                  <button
                    type="button"
                    onClick={() => {
                      void changePathologyHeatmap(pred.pathology)
                    }}
                    aria-pressed={isSelected}
                    title={`Show heatmap for ${pred.pathology}`}
                    className={cn(
                      'w-full cursor-pointer border-l-2 px-4 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-border-focus',
                      isSelected ? 'border-accent-brand bg-bg-elevated' : 'border-transparent hover:bg-bg-elevated/60'
                    )}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-[13px] font-medium text-text-primary">{pred.pathology}</span>
                      <span className={cn('font-mono text-[13px] tabular-nums', t.text)}>{formatScore(score)}</span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-3">
                      <div className="relative h-1 flex-1 rounded-[1px] bg-bg-elevated">
                        <div className={cn('h-full rounded-[1px]', t.bar)} style={{ width: `${score * 100}%` }} />
                        <div
                          aria-hidden="true"
                          className="absolute -top-1 h-3 w-px bg-text-secondary"
                          style={{ left: `${SCORE_THRESHOLD * 100}%` }}
                        />
                      </div>
                      <span className={cn('w-[118px] shrink-0 text-right text-xs', t.text)}>
                        {scoreVerdict(pred)}
                        {isBorderline(score) && <span className="text-text-muted"> · borderline</span>}
                      </span>
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
          <p className="px-4 pt-2 pb-3 text-xs leading-snug text-text-muted">
            {SCORE_EXPLANATION} The tick marks the threshold. Select a finding to show its heatmap.
          </p>
        </>
      )}
    </section>
  )
}
