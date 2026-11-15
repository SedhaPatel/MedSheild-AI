import { useEffect, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { fetchAuthOptions } from '@/lib/api'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

interface DemoAccount {
  role: string
  name: string
  canDo: string
  username: string
  password: string
}

// Only offered when the server reports demo accounts are enabled (development, or explicitly in production)
const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    role: 'Clinician',
    name: 'Dr. Sterling',
    canDo: 'Upload and read own studies, viewer, scan chat',
    username: 'dr_sterling',
    password: 'ClinicianSec2026!',
  },
  {
    role: 'Privacy officer',
    name: 'Clara Vance',
    canDo: 'Audit all studies, erase studies',
    username: 'officer_clara',
    password: 'PrivacySec2026!',
  },
  {
    role: 'Administrator',
    name: 'Security admin',
    canDo: 'Everything, including user management',
    username: 'admin_sec',
    password: 'AdminSec2026!',
  },
]

const inputClass =
  'h-9 w-full rounded-[var(--control-radius)] border border-border-strong bg-bg-panel px-3 text-[13px] text-text-primary placeholder:text-text-muted focus-visible:outline-2 focus-visible:outline-border-focus disabled:opacity-60'

export function LoginPage() {
  const login = useWorkstationStore((s) => s.login)
  const isLoading = useWorkstationStore((s) => s.isLoading)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [demoEnabled, setDemoEnabled] = useState(false)

  useEffect(() => {
    fetchAuthOptions()
      .then((opts) => setDemoEnabled(opts.demo_accounts_enabled))
      .catch(() => setDemoEnabled(false))
  }, [])

  const signIn = async (user: string, pass: string) => {
    setErrorMsg(null)
    const success = await login(user, pass)
    if (!success) setErrorMsg('Incorrect username or password.')
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) {
      setErrorMsg('Enter your username and password.')
      return
    }
    await signIn(username.trim(), password)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-canvas px-4 py-10 text-[13px] text-text-primary">
      <div className="w-full max-w-sm space-y-5">
        <div>
          <div className="text-[17px] leading-6 font-semibold tracking-tight">MedShield</div>
          <div className="text-xs text-text-muted">Chest X-ray triage</div>
        </div>

        <section className="rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel">
          <h1 className="border-b border-border-subtle px-4 py-3 text-[15px] font-semibold">Sign in</h1>
          <form onSubmit={handleSubmit} className="space-y-3 px-4 py-4">
            {errorMsg && (
              <p role="alert" className="text-accent-critical">
                {errorMsg}
              </p>
            )}
            <div>
              <label htmlFor="username" className="mb-1 block text-xs text-text-secondary">
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={inputClass}
                disabled={isLoading}
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1 block text-xs text-text-secondary">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
                disabled={isLoading}
              />
            </div>
            <Button type="submit" variant="primary" className="w-full" size="lg" disabled={isLoading}>
              {isLoading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </section>

        {demoEnabled && (
          <section className="rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel">
            <div className="border-b border-border-subtle px-4 py-2.5">
              <h2 className="text-[13px] font-semibold">Demo accounts</h2>
              <p className="text-xs text-text-muted">For testing only. Select one to sign in.</p>
            </div>
            <ul className="divide-y divide-border-subtle">
              {DEMO_ACCOUNTS.map((account) => (
                <li key={account.username}>
                  <button
                    type="button"
                    disabled={isLoading}
                    onClick={() => {
                      setUsername(account.username)
                      setPassword(account.password)
                      void signIn(account.username, account.password)
                    }}
                    className="flex w-full cursor-pointer items-baseline justify-between gap-3 px-4 py-2.5 text-left transition-colors hover:bg-bg-elevated focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-border-focus disabled:opacity-50"
                  >
                    <span>
                      <span className="block font-medium">{account.role}</span>
                      <span className="block text-xs text-text-muted">{account.canDo}</span>
                    </span>
                    <span className="shrink-0 font-mono text-xs text-text-secondary">{account.username}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <p className="text-xs leading-snug text-text-muted">
          Research and demo use only. Not a diagnostic device.
        </p>
      </div>
    </div>
  )
}
