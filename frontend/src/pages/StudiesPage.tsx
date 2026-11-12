import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { IngestionDropzone } from '@/components/sidebar/IngestionDropzone'
import { PriorityLabel } from '@/components/study/PriorityLabel'
import { StudyDetail } from '@/components/study/StudyDetail'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { formatScore, isBorderline, SCORE_THRESHOLD } from '@/lib/scores'
import { useWorkstationStore } from '@/stores/useWorkstationStore'
import type { TriageUrgency, WorklistEntry } from '@/types/clinical'

type Filter = 'ALL' | TriageUrgency | 'ERASED'

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'STAT_CRITICAL', label: 'STAT' },
  { value: 'ELEVATED', label: 'Elevated' },
  { value: 'ROUTINE', label: 'Routine' },
  { value: 'ERASED', label: 'Erased' },
]

function matchesFilter(entry: WorklistEntry, filter: Filter) {
  if (filter === 'ALL') return true
  if (filter === 'ERASED') return entry.is_shredded
  return !entry.is_shredded && entry.overall_triage_urgency === filter
}

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })

function ResultCell({ entry }: { entry: WorklistEntry }) {
  if (entry.is_shredded) return <span className="text-text-muted">—</span>
  const positive = entry.top_probability >= SCORE_THRESHOLD
  return (
    <span className={cn('whitespace-nowrap', positive ? 'text-text-primary' : 'text-text-secondary')}>
      {positive ? entry.top_pathology : 'No positive finding'}
      <span className="ml-2 font-mono text-xs text-text-muted tabular-nums">
        {formatScore(entry.top_probability)}
        {isBorderline(entry.top_probability) && ' borderline'}
      </span>
    </span>
  )
}

export function StudiesPage() {
  const samples = useWorkstationStore((s) => s.samples)
  const worklist = useWorkstationStore((s) => s.worklist)
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const ingestSample = useWorkstationStore((s) => s.ingestSample)
  const selectWorklistStudy = useWorkstationStore((s) => s.selectWorklistStudy)

  const [filter, setFilter] = useState<Filter>('ALL')
  const [query, setQuery] = useState('')

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return worklist.filter(
      (e) =>
        matchesFilter(e, filter) &&
        (!q ||
          e.file_name.toLowerCase().includes(q) ||
          e.top_pathology.toLowerCase().includes(q) ||
          e.anonymous_study_instance_uid.includes(q))
    )
  }, [worklist, filter, query])

  const counts = useMemo(
    () => Object.fromEntries(FILTERS.map((f) => [f.value, worklist.filter((e) => matchesFilter(e, f.value)).length])),
    [worklist]
  )

  return (
    <div className="flex flex-1 flex-col xl:h-screen xl:overflow-hidden">
      <PageHeader
        title="Studies"
        description="Chest X-rays de-identified, encrypted and scored by the model. Sorted by priority."
        actions={
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search file, finding or UID"
              aria-label="Search studies"
              className="h-8 w-64 rounded-[var(--control-radius)] border border-border-strong bg-bg-panel pr-3 pl-8 text-[13px] placeholder:text-text-muted focus-visible:outline-2 focus-visible:outline-border-focus"
            />
          </div>
        }
      />

      <div className="grid min-h-0 flex-1 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_400px]">
        {/* Study list */}
        <section aria-label="Study list" className="flex min-h-0 min-w-0 flex-col">
          <div className="space-y-2 px-6 pt-4 pb-3">
            <IngestionDropzone compact />
            {samples.length > 0 && (
              <p className="text-xs text-text-muted">
                Or load a sample:{' '}
                {samples.map((s, i) => (
                  <span key={s.id}>
                    {i > 0 && ' · '}
                    <button
                      type="button"
                      onClick={() => {
                        void ingestSample(s.id)
                      }}
                      className="cursor-pointer text-accent-brand hover:underline"
                    >
                      {s.id.replace(/^patient_\d+_/, '').replace(/_/g, ' ')}
                    </button>
                  </span>
                ))}
              </p>
            )}
          </div>

          <div className="flex items-center gap-1 border-b border-border-subtle px-6" role="tablist" aria-label="Filter by priority">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                role="tab"
                aria-selected={filter === f.value}
                onClick={() => setFilter(f.value)}
                className={cn(
                  '-mb-px cursor-pointer border-b-2 px-2.5 py-2 text-[13px] transition-colors',
                  filter === f.value
                    ? 'border-text-primary font-medium text-text-primary'
                    : 'border-transparent text-text-muted hover:text-text-primary'
                )}
              >
                {f.label}
                <span className="ml-1.5 text-xs text-text-muted tabular-nums">{counts[f.value]}</span>
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1 overflow-auto bg-bg-panel">
            <Table className="table-fixed">
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-32 pl-6">Priority</TableHead>
                  <TableHead className="w-[46%]">Study</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead className="w-28 pr-6 text-right">Added</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={4} className="px-6 py-10 text-center text-text-muted">
                      {worklist.length === 0
                        ? 'No studies yet. Upload a chest X-ray or load a sample above.'
                        : 'No studies match this filter.'}
                    </TableCell>
                  </TableRow>
                ) : (
                  rows.map((entry) => {
                    const isOpen = activeStudy?.anonymous_study_instance_uid === entry.anonymous_study_instance_uid
                    return (
                      <TableRow
                        key={entry.anonymous_study_instance_uid}
                        aria-selected={isOpen}
                        tabIndex={entry.is_shredded ? -1 : 0}
                        onClick={() => {
                          if (!entry.is_shredded && !isOpen) void selectWorklistStudy(entry.anonymous_study_instance_uid)
                        }}
                        onKeyDown={(e) => {
                          if ((e.key === 'Enter' || e.key === ' ') && !entry.is_shredded) {
                            e.preventDefault()
                            void selectWorklistStudy(entry.anonymous_study_instance_uid)
                          }
                        }}
                        className={cn(
                          'focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-border-focus',
                          entry.is_shredded ? 'text-text-muted' : 'cursor-pointer',
                          isOpen && 'bg-accent-brand-soft hover:bg-accent-brand-soft'
                        )}
                      >
                        <TableCell className="pl-6">
                          <PriorityLabel urgency={entry.overall_triage_urgency} erased={entry.is_shredded} />
                        </TableCell>
                        <TableCell>
                          <div className="truncate font-medium text-text-primary">{entry.file_name}</div>
                          <div className="truncate font-mono text-xs text-text-muted">
                            {entry.modality} · {entry.anonymous_study_instance_uid.slice(0, 24)}…
                          </div>
                        </TableCell>
                        <TableCell>
                          <ResultCell entry={entry} />
                        </TableCell>
                        <TableCell className="pr-6 text-right whitespace-nowrap text-text-muted tabular-nums">
                          {timeFormat.format(new Date(entry.ingested_at_utc))}
                        </TableCell>
                      </TableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </section>

        {/* Detail */}
        <aside
          aria-label="Selected study"
          className="min-h-0 overflow-y-auto border-t border-border-subtle bg-bg-panel xl:border-t-0 xl:border-l"
        >
          <StudyDetail />
        </aside>
      </div>
    </div>
  )
}
