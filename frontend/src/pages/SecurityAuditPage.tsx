import { useNavigate } from 'react-router-dom'
import { Download, Eye, ShieldCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { SafeHarborTable } from '@/components/audit/SafeHarborTable'
import { EnvelopeInspector } from '@/components/security/EnvelopeInspector'
import { CryptoShredDialog } from '@/components/security/CryptoShredDialog'
import { getDicomDownloadUrl } from '@/lib/api'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function SecurityAuditPage() {
  const navigate = useNavigate()
  const samples = useWorkstationStore((s) => s.samples)
  const worklist = useWorkstationStore((s) => s.worklist)
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const ingestSample = useWorkstationStore((s) => s.ingestSample)
  const selectWorklistStudy = useWorkstationStore((s) => s.selectWorklistStudy)

  return (
    <main className="mx-auto w-full max-w-[1600px] flex-1 space-y-6 px-4 py-6 sm:px-6">
      {/* Header Strip */}
      <div className="flex flex-col justify-between gap-3 rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel p-5 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-accent-verified" aria-hidden="true" />
            <span className="text-[11px] font-semibold tracking-wide text-accent-verified uppercase">
              Privacy Officer &amp; KMS Vault
            </span>
          </div>
          <h1 className="mt-1 font-display text-xl font-bold tracking-tight text-text-primary">
            HIPAA Safe Harbor Audit &amp; DPDP Cryptographic Erasure
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {worklist.length > 0 ? (
            <Select
              value={activeStudy?.anonymous_study_instance_uid ?? ''}
              onValueChange={(uid) => {
                void selectWorklistStudy(uid)
              }}
            >
              <SelectTrigger aria-label="Select study to audit" className="min-w-[210px]">
                <SelectValue placeholder="Choose study" />
              </SelectTrigger>
              <SelectContent>
                {worklist.map((entry) => (
                  <SelectItem
                    key={entry.anonymous_study_instance_uid}
                    value={entry.anonymous_study_instance_uid}
                  >
                    {entry.file_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            samples[0] && (
              <Button
                variant="soft"
                onClick={() => {
                  void ingestSample(samples[0].id)
                }}
              >
                Load Reference Study
              </Button>
            )
          )}

          {activeStudy && (
            <>
              <a
                href={getDicomDownloadUrl(activeStudy.anonymous_study_instance_uid, true)}
                className="inline-flex h-8 items-center gap-1.5 rounded-[var(--control-radius)] border border-accent-brand-border bg-accent-brand-soft px-3 text-xs font-medium text-accent-brand-hover transition-colors hover:bg-accent-info-soft"
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Download Clean .dcm</span>
              </a>
              <Button variant="outline" onClick={() => navigate('/workstation')}>
                <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                <span>PACS Viewer</span>
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Burned-in Pixel PHI Verification Strip */}
      {activeStudy && (
        <section
          aria-label="Pixel PHI Sanitization Comparison"
          className="grid grid-cols-1 gap-4 md:grid-cols-2"
        >
          <div className="overflow-hidden rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel">
            <div className="flex items-center justify-between border-b border-border-subtle bg-bg-input px-4 py-2.5">
              <span className="text-xs font-semibold text-text-primary">
                Pre-Ingestion Raw Radiograph
              </span>
              <Badge variant="critical">Contains Burned-in / Header PHI</Badge>
            </div>
            <div className="flex h-56 items-center justify-center bg-bg-lightbox p-3">
              <img
                src={activeStudy.images.raw_image_url}
                alt="Pre-ingestion raw scan before OCR redaction"
                className="max-h-full max-w-full rounded-[var(--viewport-radius)] border border-border-film object-contain"
              />
            </div>
          </div>

          <div className="overflow-hidden rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel">
            <div className="flex items-center justify-between border-b border-border-subtle bg-bg-input px-4 py-2.5">
              <span className="text-xs font-semibold text-text-primary">
                Post-Sanitization Clean Radiograph
              </span>
              <Badge variant="verified">
                {activeStudy.deidentification.burned_in_text_redacted
                  ? 'Pixel PHI Redacted'
                  : 'Zero Pixel PHI'}
              </Badge>
            </div>
            <div className="flex h-56 items-center justify-center bg-bg-lightbox p-3">
              <img
                src={activeStudy.images.redacted_image_url}
                alt="Post-sanitization scan with PHI scrubbed"
                className="max-h-full max-w-full rounded-[var(--viewport-radius)] border border-border-film object-contain"
              />
            </div>
          </div>
        </section>
      )}

      {/* Main Audit Matrix + AES Envelope & Erasure Console */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.45fr_390px]">
        <SafeHarborTable />

        <div className="space-y-5">
          <EnvelopeInspector />
          <CryptoShredDialog />
        </div>
      </div>
    </main>
  )
}

