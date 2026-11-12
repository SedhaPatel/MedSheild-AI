import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, ClipboardList, Lock, ShieldCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ViewerTabs } from '@/components/viewer/ViewerTabs'
import { CornerstoneViewport } from '@/components/viewer/CornerstoneViewport'
import { TriagePanel } from '@/components/diagnostics/TriagePanel'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function WorkstationPage() {
  const navigate = useNavigate()
  const samples = useWorkstationStore((s) => s.samples)
  const worklist = useWorkstationStore((s) => s.worklist)
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const ingestSample = useWorkstationStore((s) => s.ingestSample)
  const selectWorklistStudy = useWorkstationStore((s) => s.selectWorklistStudy)

  const sanitizedCount =
    activeStudy?.deidentification.tag_diff_matrix.filter((r) => r.status === 'SANITIZED').length ??
    0
  const totalTags = activeStudy?.deidentification.tag_diff_matrix.length ?? 0

  return (
    <div className="flex flex-1 flex-col lg:h-[calc(100vh-57px)] lg:overflow-hidden">
      {/* Compact Workstation Study Context Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle bg-bg-panel px-4 py-2 sm:px-6">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-display text-xs font-semibold text-text-primary">
            PACS Reading Room
          </span>

          {worklist.length > 0 ? (
            <Select
              value={activeStudy?.anonymous_study_instance_uid ?? ''}
              onValueChange={(uid) => {
                void selectWorklistStudy(uid)
              }}
            >
              <SelectTrigger aria-label="Switch active study in workstation" className="min-w-[220px]">
                <SelectValue placeholder="Choose ingested study" />
              </SelectTrigger>
              <SelectContent>
                {worklist.map((entry) => (
                  <SelectItem
                    key={entry.anonymous_study_instance_uid}
                    value={entry.anonymous_study_instance_uid}
                  >
                    {entry.file_name} — {entry.top_pathology}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            samples.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                {samples.map((sample) => (
                  <Button
                    key={sample.id}
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      void ingestSample(sample.id)
                    }}
                  >
                    Load {sample.name.replace(/^Patient \d+: /, '')}
                  </Button>
                ))}
              </div>
            )
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => navigate('/worklist')}>
            <ClipboardList className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Queue &amp; Ingest</span>
          </Button>
          {activeStudy && (
            <Button size="sm" variant="soft" onClick={() => navigate('/security')}>
              <Lock className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Security Vault</span>
            </Button>
          )}
        </div>
      </div>

      {/* Main Two-Column Reading Area */}
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[1fr_340px]">
        {/* Left/Center Viewport Focal Stage */}
        <main className="flex min-w-0 flex-col bg-bg-canvas">
          <ViewerTabs />
          <CornerstoneViewport />

          {/* Concise Bottom Safe Harbor & UID Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle bg-bg-panel px-4 py-2 text-xs">
            {activeStudy ? (
              <>
                <div className="flex flex-wrap items-center gap-2.5">
                  <ShieldCheck className="h-4 w-4 text-accent-verified" aria-hidden="true" />
                  <span className="font-medium text-text-primary">
                    {sanitizedCount}/{totalTags} Safe Harbor Tags Redacted
                  </span>
                  <span className="text-text-muted">&middot;</span>
                  <span className="font-mono text-[11px] text-text-muted">
                    H={activeStudy.security.shannon_entropy_bits_per_byte.toFixed(4)} bits/B
                  </span>
                </div>
                <Link
                  to="/security"
                  className="inline-flex items-center gap-1 font-medium text-accent-brand hover:text-accent-brand-hover"
                >
                  <span>Inspect 18-tag diff &amp; erasure</span>
                  <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                </Link>
              </>
            ) : (
              <span className="text-text-muted">
                Select a reference clinical case above or ingest a DICOM scan to begin interactive window/level inspection.
              </span>
            )}
          </div>
        </main>

        {/* Right Clinical Triage & Shortcuts Rail */}
        <aside
          aria-label="Diagnostic triage and workstation shortcuts"
          className="flex flex-col gap-4 overflow-y-auto border-t border-border-subtle bg-bg-canvas p-4 lg:border-t-0 lg:border-l"
        >
          <TriagePanel />

          <section className="rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel p-4">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-xs font-semibold text-text-primary">
                Envelope Seal Status
              </h2>
              <Badge variant="verified">
                {activeStudy ? 'Sealed' : 'Idle'}
              </Badge>
            </div>
            <p className="mt-2 font-mono text-[11px] break-all text-text-secondary">
              {activeStudy
                ? `SHA-256: ${activeStudy.security.sha256_hash.slice(0, 28)}...`
                : 'Awaiting study ingestion'}
            </p>
            {activeStudy && (
              <Button
                variant="outline"
                size="sm"
                className="mt-3 w-full"
                onClick={() => navigate('/security')}
              >
                <Lock className="h-3 w-3" aria-hidden="true" />
                <span>Manage Security &amp; Erasure</span>
              </Button>
            )}
          </section>

          <section className="rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel p-4">
            <h2 className="font-display text-xs font-semibold text-text-primary">
              Reading Shortcuts
            </h2>
            <dl className="mt-2.5 grid grid-cols-[90px_1fr] gap-y-1.5 text-[11px]">
              <dt className="font-mono font-semibold whitespace-nowrap text-accent-brand-hover">[1 / 2 / 3]</dt>
              <dd className="text-text-secondary">Original / Scrubbed DICOM / Grad-CAM</dd>
              <dt className="font-mono font-semibold text-accent-brand-hover">[I]</dt>
              <dd className="text-text-secondary">Invert radiograph grayscale</dd>
              <dt className="font-mono font-semibold text-accent-brand-hover">[+ / -]</dt>
              <dd className="text-text-secondary">Step zoom in or out</dd>
              <dt className="font-mono font-semibold text-accent-brand-hover">[0 / R]</dt>
              <dd className="text-text-secondary">Reset camera &amp; W/L</dd>
            </dl>
          </section>
        </aside>
      </div>
    </div>
  )
}

