import { Activity } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function TriagePanel() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const targetPathology = useWorkstationStore((s) => s.targetPathology)
  const changePathologyHeatmap = useWorkstationStore((s) => s.changePathologyHeatmap)

  return (
    <section
      aria-label="AI Diagnostic Triage"
      className="overflow-hidden rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel"
    >
      <div className="flex items-center justify-between border-b border-border-subtle bg-bg-input px-4 py-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-text-primary">
          <Activity className="h-4 w-4 text-accent-brand" aria-hidden="true" />
          <span>Diagnostic Triage</span>
        </div>
        <span className="font-mono text-[11px] text-text-muted tabular-nums">
          {activeStudy ? `${activeStudy.ai_diagnostics.inference_latency_ms} ms` : '-- ms'}
        </span>
      </div>

      <div className="p-3">
        {!activeStudy ? (
          <div className="py-5 text-center text-xs text-text-muted">
            Awaiting inference
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {activeStudy.ai_diagnostics.predictions.map((pred) => {
              const pct = (pred.probability * 100).toFixed(1)
              const isSelected = targetPathology === pred.pathology
              const barColor =
                pred.probability >= 0.7
                  ? 'bg-accent-critical'
                  : pred.probability >= 0.45
                    ? 'bg-accent-attention'
                    : 'bg-accent-info'
              const textColor =
                pred.probability >= 0.7
                  ? 'text-accent-critical'
                  : pred.probability >= 0.45
                    ? 'text-accent-attention'
                    : 'text-text-primary'

              return (
                <button
                  key={pred.pathology}
                  type="button"
                  onClick={() => {
                    void changePathologyHeatmap(pred.pathology)
                  }}
                  title={`Localize ${pred.pathology} Grad-CAM saliency`}
                    className={cn(
                      'grid w-full cursor-pointer grid-cols-[1fr_76px_46px] items-center gap-2 rounded-[var(--control-radius)] border px-2.5 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-border-focus',
                      isSelected
                        ? 'border-accent-brand-border bg-accent-brand-soft'
                        : 'border-transparent hover:bg-bg-elevated'
                    )}
                  >
                    <div>
                      <div className="text-xs font-medium text-text-primary">
                        {pred.pathology}
                      </div>
                      <div className="font-mono text-[10px] text-text-muted tabular-nums">
                        &plusmn;{pred.epistemic_uncertainty.toFixed(3)} unc.
                      </div>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-border-subtle">
                      <div
                        className={cn('h-full rounded-full transition-all duration-300', barColor)}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  <div className={cn('text-right font-mono text-xs font-semibold tabular-nums', textColor)}>
                    {pct}%
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}

