import { Panel } from '@/components/layout/Panel'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'
import type { PiiTagDiff } from '@/types/clinical'

function outcome(row: PiiTagDiff): { label: string; className: string } {
  if (row.status === 'SANITIZED') {
    return row.sanitized_value.startsWith('[SCRUBBED')
      ? { label: 'Removed', className: 'text-accent-verified' }
      : { label: 'Replaced', className: 'text-accent-verified' }
  }
  if (row.status === 'MODIFIED') {
    return row.sanitized_value.trim() === ''
      ? { label: 'Emptied', className: 'text-accent-verified' }
      : { label: 'Changed', className: 'text-text-secondary' }
  }
  return { label: 'Unchanged', className: 'text-text-muted' }
}

export function SafeHarborTable() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const rows = activeStudy?.deidentification.tag_diff_matrix ?? []
  const violations = activeStudy?.deidentification.compliance_violations ?? []

  return (
    <Panel
      title="Metadata de-identification"
      aside={activeStudy ? activeStudy.deidentification.safe_harbor_compliance.toLowerCase() : undefined}
    >
      <Table className="min-w-[600px] sm:min-w-full sm:table-fixed">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-28 pl-4">Tag</TableHead>
            <TableHead className="w-44">Attribute</TableHead>
            <TableHead>Original value</TableHead>
            <TableHead>Stored value</TableHead>
            <TableHead className="w-24 pr-4 text-right">Result</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const o = outcome(row)
            const removed = row.sanitized_value.startsWith('[SCRUBBED')
            const emptied = !removed && row.sanitized_value.trim() === ''
            return (
              <TableRow key={row.tag_hex}>
                <TableCell className="pl-4 font-mono text-xs text-text-muted">{row.tag_hex}</TableCell>
                <TableCell className="truncate text-text-primary" title={row.description}>
                  {row.tag_name}
                </TableCell>
                <TableCell className="truncate font-mono text-xs text-text-secondary" title={row.original_value}>
                  {row.original_value}
                </TableCell>
                <TableCell
                  className={cn('truncate font-mono text-xs', removed || emptied ? 'text-text-muted italic' : 'text-text-primary')}
                  title={row.sanitized_value}
                >
                  {removed ? 'removed' : emptied ? 'empty' : row.sanitized_value}
                </TableCell>
                <TableCell className={cn('pr-4 text-right', o.className)}>{o.label}</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      {violations.length > 0 && (
        <ul className="border-t border-border-subtle px-4 py-2.5 text-xs text-accent-critical">
          {violations.map((v) => (
            <li key={v}>{v}</li>
          ))}
        </ul>
      )}
      <p className="border-t border-border-subtle px-4 py-2.5 text-xs text-text-muted">
        Original values are held in server memory for this session only and are never written to disk; the stored,
        encrypted file contains only the de-identified values.
      </p>
    </Panel>
  )
}
