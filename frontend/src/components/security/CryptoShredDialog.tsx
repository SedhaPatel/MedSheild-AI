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
import { Panel } from '@/components/layout/Panel'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function CryptoShredDialog() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const worklist = useWorkstationStore((s) => s.worklist)
  const cryptoShredActiveStudy = useWorkstationStore((s) => s.cryptoShredActiveStudy)
  const user = useWorkstationStore((s) => s.user)

  const activeUid = activeStudy?.anonymous_study_instance_uid ?? null
  const isShredded = Boolean(
    activeUid && worklist.find((w) => w.anonymous_study_instance_uid === activeUid)?.is_shredded
  )
  // Matches the backend rule (require_privacy_officer): privacy officers and administrators may erase
  const canErase = user?.role === 'privacy_officer' || user?.role === 'admin'

  return (
    <Panel title="Erase study" aside="DPDP Act Sec. 12">
      <div className="space-y-3 px-4 py-3 text-[13px]">
        <p className={isShredded ? 'text-accent-critical' : 'text-text-secondary'}>
          {isShredded
            ? 'Erased. The study key was destroyed and the stored file can no longer be decrypted.'
            : 'Destroys this study\'s encryption key. The stored file stays on disk but becomes unreadable. Other studies are not affected.'}
        </p>
        {!canErase && !isShredded && (
          <p className="text-xs text-text-muted">
            Only a privacy officer or administrator can erase studies. You are signed in as{' '}
            {user?.role.replace('_', ' ') ?? 'a guest'}.
          </p>
        )}
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="destructive"
              disabled={!activeStudy || isShredded || !canErase}
            >
              Erase study…
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                Erase this study?
              </AlertDialogTitle>
              <AlertDialogDescription>
                This destroys the encryption key for{' '}
                <span className="font-medium text-text-primary">{activeStudy?.file_name}</span> (right to erasure,
                India DPDP Act 2023 Sec. 12). The stored file can never be decrypted again. This cannot be undone.
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
                  Erase permanently
                </Button>
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </Panel>
  )
}

