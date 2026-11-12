import type { ReactNode } from 'react'

/** Bordered section with a plain title row; the standard container for audit content. */
export function Panel({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel">
      <div className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-2.5">
        <h2 className="text-[13px] font-semibold text-text-primary">{title}</h2>
        {aside && <div className="text-xs text-text-muted">{aside}</div>}
      </div>
      {children}
    </section>
  )
}
