import { cn } from '@/lib/utils'
import type { TriageUrgency } from '@/types/clinical'

const LABELS: Record<TriageUrgency | 'ERASED', { text: string; dot: string; textClass: string }> = {
  STAT_CRITICAL: { text: 'STAT', dot: 'bg-accent-critical', textClass: 'text-accent-critical font-semibold' },
  ELEVATED: { text: 'Elevated', dot: 'bg-accent-attention', textClass: 'text-accent-attention font-medium' },
  ROUTINE: { text: 'Routine', dot: 'bg-text-muted/50', textClass: 'text-text-secondary' },
  ERASED: { text: 'Erased', dot: 'border border-text-muted bg-transparent', textClass: 'text-text-muted' },
}

/** One consistent way to show triage priority: a small dot plus a word, no pill. */
export function PriorityLabel({
  urgency,
  erased = false,
  className,
}: {
  urgency: TriageUrgency
  erased?: boolean
  className?: string
}) {
  const meta = LABELS[erased ? 'ERASED' : urgency]
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-[13px] whitespace-nowrap', meta.textClass, className)}>
      <span aria-hidden="true" className={cn('h-2 w-2 shrink-0 rounded-full', meta.dot)} />
      {meta.text}
    </span>
  )
}
