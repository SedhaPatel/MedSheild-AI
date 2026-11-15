import type { ReactNode } from 'react'

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-border-subtle bg-bg-panel px-6 py-3">
      <div className="min-w-0">
        <h1 className="text-[15px] leading-6 font-semibold text-text-primary">{title}</h1>
        {description && <p className="truncate text-xs text-text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}
