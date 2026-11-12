import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/layout/PageHeader'
import { Panel } from '@/components/layout/Panel'
import { StudyPicker } from '@/components/layout/StudyPicker'
import { SafeHarborTable } from '@/components/audit/SafeHarborTable'
import { EnvelopeInspector } from '@/components/security/EnvelopeInspector'
import { CryptoShredDialog } from '@/components/security/CryptoShredDialog'
import { getDicomDownloadUrl } from '@/lib/api'
import { selectIsActiveStudyShredded, useWorkstationStore } from '@/stores/useWorkstationStore'

const PIPELINE_STEPS: [string, string][] = [
  ['Ingest', 'A DICOM file is read as-is; PNG/JPEG images are wrapped in a DICOM container.'],
  [
    'De-identify',
    'Identifying metadata tags are removed, UIDs are replaced with salted HMAC pseudonyms, dates are shifted per patient, and burned-in text in the image margins is blacked out.',
  ],
  ['Encrypt', 'The de-identified file is encrypted with a per-study AES-256-GCM key, which is itself wrapped by a key-encryption key.'],
  ['Score', 'The image is decrypted in memory only and scored by the DenseNet-121 model; heatmaps show which regions influenced each finding.'],
]

export function SecurityAuditPage() {
  const navigate = useNavigate()
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const isShredded = useWorkstationStore(selectIsActiveStudyShredded)

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="Audit"
        description={
          activeStudy
            ? `De-identification and encryption record for ${activeStudy.file_name}`
            : 'De-identification and encryption record'
        }
        actions={
          <>
            <StudyPicker />
            {activeStudy && !isShredded && (
              <>
                <a
                  href={getDicomDownloadUrl(activeStudy.anonymous_study_instance_uid, true)}
                  className="inline-flex h-8 items-center rounded-[var(--control-radius)] border border-border-strong bg-bg-panel px-3 text-[13px] font-medium text-text-primary hover:bg-bg-elevated focus-visible:outline-2 focus-visible:outline-border-focus"
                >
                  Download .dcm
                </a>
                <Button variant="ghost" onClick={() => navigate('/workstation')}>
                  Open in viewer
                </Button>
              </>
            )}
          </>
        }
      />

      <main className="w-full max-w-[1400px] space-y-5 px-6 py-5">
        {!activeStudy ? (
          <p className="text-[13px] text-text-muted">
            No study open. Choose one above, or upload one on the Studies page.
          </p>
        ) : (
          <>
            <Panel
              title="Pixel de-identification"
              aside={
                activeStudy.deidentification.burned_in_text_redacted
                  ? 'Burned-in text found and blacked out'
                  : 'No burned-in text detected'
              }
            >
              <div className="grid grid-cols-1 divide-y divide-border-subtle md:grid-cols-2 md:divide-x md:divide-y-0">
                {[
                  { src: activeStudy.images.raw_image_url, caption: 'As uploaded' },
                  { src: activeStudy.images.redacted_image_url, caption: 'As stored (de-identified)' },
                ].map((img) => (
                  <figure key={img.caption} className="p-3">
                    <div className="flex h-64 items-center justify-center bg-bg-lightbox">
                      <img src={img.src} alt={img.caption} className="max-h-full max-w-full object-contain" />
                    </div>
                    <figcaption className="mt-2 text-xs text-text-muted">{img.caption}</figcaption>
                  </figure>
                ))}
              </div>
            </Panel>

            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
              <SafeHarborTable />
              <div className="space-y-5">
                <EnvelopeInspector />
                <CryptoShredDialog />
              </div>
            </div>
          </>
        )}

        <Panel title="How a study is processed">
          <ol className="divide-y divide-border-subtle text-[13px]">
            {PIPELINE_STEPS.map(([name, text], i) => (
              <li key={name} className="grid grid-cols-[28px_110px_1fr] gap-2 px-4 py-2.5">
                <span className="text-text-muted tabular-nums">{i + 1}.</span>
                <span className="font-medium text-text-primary">{name}</span>
                <span className="text-text-secondary">{text}</span>
              </li>
            ))}
          </ol>
          <p className="border-t border-border-subtle px-4 py-2.5 text-xs text-text-muted">
            Dates are shifted rather than reduced to the year, so date handling follows HIPAA Expert Determination rather
            than strict Safe Harbor. Keys are held by a local simulated KMS; use a managed KMS/HSM in production.
          </p>
        </Panel>
      </main>
    </div>
  )
}
