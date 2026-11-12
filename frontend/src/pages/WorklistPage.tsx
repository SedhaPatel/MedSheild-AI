import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, Lock, Search } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { IngestionDropzone } from '@/components/sidebar/IngestionDropzone'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'
import type { TriageUrgency } from '@/types/clinical'

type FilterUrgency = 'ALL' | TriageUrgency | 'SHREDDED'

const FILTER_OPTIONS: { value: FilterUrgency; label: string }[] = [
  { value: 'ALL', label: 'All Studies' },
  { value: 'STAT_CRITICAL', label: 'STAT Critical' },
  { value: 'ELEVATED', label: 'Elevated' },
  { value: 'ROUTINE', label: 'Routine' },
  { value: 'SHREDDED', label: 'Erased' },
]

export function WorklistPage() {
  const navigate = useNavigate()
  const samples = useWorkstationStore((s) => s.samples)
  const worklist = useWorkstationStore((s) => s.worklist)
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const activeSampleId = useWorkstationStore((s) => s.activeSampleId)
  const ingestSample = useWorkstationStore((s) => s.ingestSample)
  const selectWorklistStudy = useWorkstationStore((s) => s.selectWorklistStudy)

  const [urgencyFilter, setUrgencyFilter] = useState<FilterUrgency>('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  const filteredWorklist = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return worklist.filter((entry) => {
      if (urgencyFilter === 'SHREDDED' && !entry.is_shredded) return false
      if (
        urgencyFilter !== 'ALL' &&
        urgencyFilter !== 'SHREDDED' &&
        (entry.is_shredded || entry.overall_triage_urgency !== urgencyFilter)
      ) {
        return false
      }
      if (!q) return true
      return (
        entry.file_name.toLowerCase().includes(q) ||
        entry.top_pathology.toLowerCase().includes(q) ||
        entry.anonymous_study_instance_uid.toLowerCase().includes(q) ||
        entry.modality.toLowerCase().includes(q)
      )
    })
  }, [worklist, urgencyFilter, searchQuery])

  async function openStudyRoute(studyUid: string, targetPath: '/workstation' | '/security') {
    await selectWorklistStudy(studyUid)
    navigate(targetPath)
  }

  return (
    <main className="mx-auto w-full max-w-[1600px] flex-1 space-y-6 px-4 py-6 sm:px-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h1 className="font-display text-xl font-bold tracking-tight text-text-primary">
            Study Ingestion &amp; Clinical Triage Worklist
          </h1>
          <p className="mt-0.5 text-xs text-text-secondary">
            Upload raw DICOM files or select reference studies; queue automatically prioritizes STAT findings before routine screenings.
          </p>
        </div>
        {activeStudy && (
          <Button variant="primary" onClick={() => navigate('/workstation')}>
            <Eye className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Inspect Active Study</span>
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[310px_1fr]">
        {/* Left Sidebar: Dropzone + Reference Sample Cards */}
        <aside className="space-y-5">
          <div className="rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel p-4">
            <IngestionDropzone />
          </div>

          <section className="rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-display text-xs font-semibold tracking-wide text-text-primary uppercase">
                Reference Clinical Cases
              </h2>
              <span className="font-mono text-[11px] text-text-muted">
                {samples.length} cases
              </span>
            </div>

            <div className="flex flex-col gap-2">
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
                      'w-full cursor-pointer rounded-[var(--control-radius)] border px-3 py-2.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-border-focus',
                      isSelected
                        ? 'border-accent-brand-border bg-accent-brand-soft'
                        : 'border-border-subtle bg-bg-input hover:border-border-strong hover:bg-bg-elevated'
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
          </section>
        </aside>

        {/* Right Main Worklist Table Card */}
        <section className="flex flex-col overflow-hidden rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel">
          <div className="flex flex-col justify-between gap-3 border-b border-border-subtle bg-bg-input px-4 py-3 sm:flex-row sm:items-center">
            <div className="flex flex-wrap items-center gap-1.5">
              {FILTER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setUrgencyFilter(opt.value)}
                  className={cn(
                    'cursor-pointer rounded-[var(--control-radius)] border px-2.5 py-1 text-[11px] font-medium transition-colors',
                    urgencyFilter === opt.value
                      ? 'border-accent-brand-border bg-accent-brand-soft font-semibold text-accent-brand-hover'
                      : 'border-border-subtle bg-bg-panel text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="relative w-full sm:w-64">
              <Search
                className="pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-text-muted"
                aria-hidden="true"
              />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search study, pathology, UID..."
                aria-label="Search worklist studies"
                className="h-8 w-full rounded-[var(--control-radius)] border border-border-strong bg-bg-panel pr-3 pl-8 text-xs text-text-primary placeholder:text-text-muted focus-visible:outline-2 focus-visible:outline-border-focus"
              />
            </div>
          </div>

          <Table className="min-w-[680px] sm:min-w-full">
            <TableHeader>
              <TableRow>
                <TableHead>Study File / Anonymous UID</TableHead>
                <TableHead>Modality</TableHead>
                <TableHead>Primary AI Finding</TableHead>
                <TableHead>Urgency</TableHead>
                <TableHead>Entropy (H)</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredWorklist.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-12 text-center text-xs text-text-muted">
                    {worklist.length === 0
                      ? 'No studies ingested yet. Select a reference case on the left or upload a DICOM study.'
                      : 'No ingested studies match the active urgency filter or search term.'}
                  </TableCell>
                </TableRow>
              ) : (
                filteredWorklist.map((entry) => {
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
                    <TableRow
                      key={entry.anonymous_study_instance_uid}
                      className={isCurrent ? 'bg-accent-brand-soft/45' : undefined}
                    >
                      <TableCell>
                        <div className="font-mono text-xs font-semibold text-text-primary">
                          {entry.file_name}
                        </div>
                        <div className="font-mono text-[10px] text-text-muted">
                          {entry.anonymous_study_instance_uid.slice(0, 32)}...
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-text-secondary">
                        {entry.modality}
                      </TableCell>
                      <TableCell className="text-text-primary tabular-nums">
                        {entry.top_pathology} ({(entry.top_probability * 100).toFixed(1)}%)
                      </TableCell>
                      <TableCell>
                        <Badge variant={urgencyVariant}>
                          {entry.is_shredded
                            ? 'Shredded'
                            : entry.overall_triage_urgency.replace('_', ' ')}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-text-secondary tabular-nums">
                        {entry.shannon_entropy.toFixed(4)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="inline-flex items-center justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant={isCurrent ? 'soft' : 'outline'}
                            onClick={() => {
                              void openStudyRoute(entry.anonymous_study_instance_uid, '/workstation')
                            }}
                          >
                            <Eye className="h-3 w-3" aria-hidden="true" />
                            <span>Inspect</span>
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              void openStudyRoute(entry.anonymous_study_instance_uid, '/security')
                            }}
                          >
                            <Lock className="h-3 w-3" aria-hidden="true" />
                            <span>Audit</span>
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </section>
      </div>
    </main>
  )
}

