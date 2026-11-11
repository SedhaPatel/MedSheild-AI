import { Trash2 } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function CryptoShredDialog() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const worklist = useWorkstationStore((s) => s.worklist)
  const cryptoShredActiveStudy = useWorkstationStore((s) => s.cryptoShredActiveStudy)

  const activeUid = activeStudy?.anonymous_study_instance_uid ?? null
  const isShredded = Boolean(
    activeUid && worklist.find((w) => w.anonymous_study_instance_uid === activeUid)?.is_shredded
  )

  return (
    <section
      aria-label="DPDP Right to Erasure"
      className="mt-auto overflow-hidden rounded-[var(--panel-radius)] border border-border-subtle bg-bg-canvas"
    >
      <div className="flex items-center justify-between border-b border-border-subtle bg-bg-panel px-3.5 py-2.5">
        <div className="flex items-center gap-1.5 text-[13px] font-semibold text-text-primary">
          <Trash2 className="h-3.5 w-3.5 text-text-secondary" aria-hidden="true" />
          <span>Right to Erasure</span>
        </div>
        <span className="text-[11px] text-text-muted">DPDP Sec. 12</span>
      </div>

      <div className="space-y-2.5 p-3.5">
        <div
          className={
            isShredded
              ? 'font-mono text-[11px] font-semibold text-accent-critical'
              : 'font-mono text-[11px] text-text-muted'
          }
        >
          {isShredded
            ? 'Crypto-shredded. Study KEK destroyed.'
            : activeStudy
              ? `Key: ${activeStudy.security.kms_master_key_id.slice(-22)}`
              : 'Study key isolated per UID'}
        </div>

        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="destructive"
              className="w-full"
              disabled={!activeStudy || isShredded}
            >
              Crypto-Shred Study
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                Confirm Irreversible Cryptographic Erasure
              </AlertDialogTitle>
              <AlertDialogDescription>
                Under India DPDP Act 2023 Section 12, this destroys the study-scoped Master KEK (
                <span className="font-mono text-text-primary">
                  {activeStudy?.security.kms_master_key_id.slice(-24)}
                </span>
                ) by overwriting key bytes with zeroes. Other ingested studies remain unaffected, while this study&apos;s DICOM payload becomes permanently undecryptable noise.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel asChild>
                <Button variant="ghost">Cancel</Button>
              </AlertDialogCancel>
              <AlertDialogAction asChild>
                <Button
                  variant="destructive"
                  onClick={() => {
                    void cryptoShredActiveStudy()
                  }}
                >
                  Destroy Study Key
                </Button>
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </section>
  )
}

