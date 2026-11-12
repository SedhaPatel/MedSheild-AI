import type { ReactNode } from 'react'
import { NavLink, Link } from 'react-router-dom'
import {
  ClipboardList,
  LayoutDashboard,
  Lock,
  Monitor,
  ShieldCheck,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

const NAV_ITEMS = [
  { to: '/', label: 'Identifier Hub', icon: LayoutDashboard, end: true },
  { to: '/worklist', label: 'Worklist Queue', icon: ClipboardList, end: false },
  { to: '/workstation', label: 'PACS Workstation', icon: Monitor, end: false },
  { to: '/security', label: 'Security & Audit', icon: Lock, end: false },
] as const

export function AppShell({ children }: { children: ReactNode }) {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const worklist = useWorkstationStore((s) => s.worklist)

  return (
    <div className="flex min-h-screen flex-col bg-bg-canvas text-[13px] text-text-primary">
      {/* Daylight Institutional Top Bar */}
      <header className="relative z-30 border-b border-border-subtle bg-bg-panel">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between gap-4 px-4 sm:px-6">
          {/* Brand Identity */}
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="flex items-center gap-2.5 rounded-[var(--control-radius)] py-1 pr-2 text-text-primary focus-visible:outline-2 focus-visible:outline-border-focus"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-[var(--control-radius)] border border-accent-brand-border bg-accent-brand-soft text-accent-brand">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              </span>
              <span className="flex flex-col leading-tight">
                <span className="font-display text-sm font-bold tracking-tight text-text-primary">
                  MedShield-AI
                </span>
                <span className="text-[10px] font-medium text-text-muted">
                  Zero-Trust Clinical Portal
                </span>
              </span>
            </Link>

            <span className="hidden h-5 w-px bg-border-subtle md:inline-block" aria-hidden="true" />

            {/* Desktop Primary Multipage Navigation */}
            <nav aria-label="Primary portal routes" className="hidden items-center gap-1 md:flex">
              {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      'inline-flex items-center gap-1.5 rounded-[var(--control-radius)] border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-border-focus',
                      isActive
                        ? 'border-accent-brand-border bg-accent-brand-soft font-semibold text-accent-brand-hover'
                        : 'border-transparent text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                    )
                  }
                >
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{label}</span>
                  {to === '/worklist' && worklist.length > 0 && (
                    <span className="ml-0.5 rounded-full bg-bg-panel px-1.5 py-0.5 font-mono text-[10px] font-semibold text-accent-brand-hover tabular-nums">
                      {worklist.length}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Right Institutional Telemetry */}
          <div className="flex items-center gap-2">
            {activeStudy ? (
              <Link
                to="/workstation"
                className="hidden items-center gap-2 rounded-[var(--control-radius)] border border-border-subtle bg-bg-input px-2.5 py-1 text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary sm:inline-flex"
                title="Jump to active study in PACS Workstation"
              >
                <span className="h-2 w-2 rounded-full bg-accent-verified" aria-hidden="true" />
                <span className="max-w-[160px] truncate font-mono text-[11px] font-medium text-text-primary">
                  {activeStudy.file_name}
                </span>
              </Link>
            ) : (
              <span className="hidden text-[11px] text-text-muted sm:inline">
                No active study
              </span>
            )}
            <div className="hidden items-center gap-1.5 xl:flex">
              <Badge variant="teal">AES-256-GCM</Badge>
              <Badge variant="verified">PS 3.15 Safe Harbor</Badge>
            </div>
          </div>
        </div>

        {/* Mobile / Compact Horizontal Navigation Strip */}
        <nav
          aria-label="Mobile portal routes"
          className="flex items-center gap-1 overflow-x-auto border-t border-border-subtle bg-bg-input px-4 py-1.5 md:hidden"
        >
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'inline-flex shrink-0 items-center gap-1.5 rounded-[var(--control-radius)] border px-2.5 py-1 text-[11px] font-medium transition-colors',
                  isActive
                    ? 'border-accent-brand-border bg-accent-brand-soft font-semibold text-accent-brand-hover'
                    : 'border-transparent text-text-secondary hover:bg-bg-panel hover:text-text-primary'
                )
              }
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{label}</span>
              {to === '/worklist' && worklist.length > 0 && (
                <span className="font-mono text-[10px] font-semibold tabular-nums">
                  ({worklist.length})
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </header>

      {/* Active Route Surface */}
      <div className="flex flex-1 flex-col">{children}</div>
    </div>
  )
}

