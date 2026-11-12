import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function SafeHarborTable({ compact = false }: { compact?: boolean }) {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)

  return (
    <section
      aria-label="DICOM PS 3.15 Safe Harbor Audit"
      className={
        compact
          ? 'flex h-56 flex-col overflow-hidden rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel'
          : 'flex flex-col overflow-hidden rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel'
      }
    >
      <div className="flex items-center justify-between border-b border-border-subtle bg-bg-input px-4 py-3">
        <h2 className="font-display text-xs font-semibold text-text-primary">
          DICOM PS 3.15 Safe Harbor Attribute Matrix
        </h2>
        {activeStudy ? (
          <Badge
            variant={
              activeStudy.deidentification.burned_in_text_redacted
                ? 'verified'
                : 'neutral'
            }
          >
            {activeStudy.deidentification.burned_in_text_redacted
              ? 'Burned-in pixel PHI redacted'
              : 'No burned-in pixel PHI'}
          </Badge>
        ) : (
          <span className="text-[11px] text-text-muted">Awaiting study</span>
        )}
      </div>

      <Table className="min-w-[600px] flex-1 sm:min-w-full sm:table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-24">Tag</TableHead>
            <TableHead className="w-40">Attribute</TableHead>
            <TableHead>Pre-Ingestion PHI</TableHead>
            <TableHead>Post-Ingestion</TableHead>
            <TableHead className="w-28 text-right">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {!activeStudy ? (
            <TableRow>
              <TableCell colSpan={5} className="py-8 text-center text-text-muted">
                Ingest a scan to verify 18 HIPAA Safe Harbor attribute sanitization.
              </TableCell>
            </TableRow>
          ) : (
            activeStudy.deidentification.tag_diff_matrix.map((row) => {
              const isScrubbed = row.status === 'SANITIZED'
              return (
                <TableRow key={row.tag_hex}>
                  <TableCell className="font-mono text-text-muted">
                    {row.tag_hex}
                  </TableCell>
                  <TableCell className="truncate font-medium text-text-primary">
                    {row.tag_name}
                  </TableCell>
                  <TableCell
                    className="truncate font-mono text-accent-critical"
                    title={row.original_value}
                  >
                    {row.original_value}
                  </TableCell>
                  <TableCell
                    className="truncate font-mono text-accent-verified"
                    title={row.sanitized_value}
                  >
                    {row.sanitized_value}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant={isScrubbed ? 'verified' : 'neutral'}>
                      {row.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              )
            })
          )}
        </TableBody>
      </Table>
    </section>
  )
}

