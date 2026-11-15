import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { FileLock2, ListChecks, LogOut, ScanLine } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

const NAV_ITEMS = [
  { to: '/', label: 'Studies', icon: ListChecks, end: true },
  { to: '/workstation', label: 'Viewer', icon: ScanLine, end: false },
  { to: '/security', label: 'Audit', icon: FileLock2, end: false },
] as const

const ROLE_LABELS: Record<string, string> = {
  clinician: 'Clinician',
  privacy_officer: 'Privacy officer',
  admin: 'Administrator',
}

function navClass(isActive: boolean) {
  return cn(
    'flex h-8 items-center gap-2.5 rounded-[var(--control-radius)] px-2.5 text-[13px] transition-colors focus-visible:outline-2 focus-visible:outline-border-focus',
    isActive
      ? 'bg-bg-elevated font-medium text-text-primary'
      : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const worklist = useWorkstationStore((s) => s.worklist)
  const user = useWorkstationStore((s) => s.user)
  const logout = useWorkstationStore((s) => s.logout)
  const studyCount = worklist.filter((w) => !w.is_shredded).length

  return (
    <div className="flex min-h-screen bg-bg-canvas text-[13px] text-text-primary">
      {/* Sidebar (md and up) */}
      <aside className="sticky top-0 hidden h-screen w-52 shrink-0 flex-col border-r border-border-subtle bg-bg-panel md:flex">
        <Link to="/" className="block border-b border-border-subtle px-4 py-3.5 focus-visible:outline-2 focus-visible:outline-border-focus">
          <span className="block text-[15px] leading-5 font-semibold tracking-tight text-text-primary">MedShield</span>
          <span className="block text-xs text-text-muted">Chest X-ray triage</span>
        </Link>

        <nav aria-label="Main" className="flex flex-col gap-0.5 p-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => navClass(isActive)}>
              <Icon className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
              <span className="flex-1">{label}</span>
              {to === '/' && studyCount > 0 && (
                <span className="text-xs text-text-muted tabular-nums">{studyCount}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto space-y-3 border-t border-border-subtle px-4 py-3.5 text-xs">
          {activeStudy && (
            <div>
              <div className="text-text-muted">Open study</div>
              <Link
                to="/workstation"
                className="block truncate font-medium text-text-primary hover:text-accent-brand"
                title={activeStudy.file_name}
              >
                {activeStudy.file_name}
              </Link>
            </div>
          )}

          {user && (
            <div className="flex items-start justify-between gap-2 border-t border-border-subtle pt-3">
              <div className="min-w-0">
                <div className="truncate font-medium text-text-primary" title={user.full_name}>
                  {user.full_name}
                </div>
                <div className="text-text-muted">{ROLE_LABELS[user.role] ?? user.role}</div>
              </div>
              <button
                type="button"
                onClick={() => void logout()}
                title="Sign out"
                aria-label="Sign out"
                className="shrink-0 cursor-pointer rounded-[var(--control-radius)] p-1 text-text-muted hover:bg-bg-elevated hover:text-text-primary focus-visible:outline-2 focus-visible:outline-border-focus"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          )}

          <p className="leading-snug text-text-muted">
            Research and demo use only. Not a diagnostic device.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Compact top bar (below md) */}
        <header className="flex items-center gap-4 border-b border-border-subtle bg-bg-panel px-4 py-2 md:hidden">
          <Link to="/" className="text-[15px] font-semibold tracking-tight">MedShield</Link>
          <nav aria-label="Main" className="flex flex-1 gap-1 overflow-x-auto">
            {NAV_ITEMS.map(({ to, label, end }) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => navClass(isActive)}>
                {label}
              </NavLink>
            ))}
          </nav>
          {user && (
            <button
              type="button"
              onClick={() => void logout()}
              aria-label="Sign out"
              className="cursor-pointer p-1 text-text-muted hover:text-text-primary"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </header>

        {children}
      </div>
    </div>
  )
}
