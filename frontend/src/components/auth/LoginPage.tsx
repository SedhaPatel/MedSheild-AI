import { useState, type FormEvent } from 'react'
import { KeyRound, Lock, ShieldCheck, UserCheck, Stethoscope, ShieldAlert, Cpu } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

interface PersonaPreset {
  name: string
  roleLabel: string
  roleVariant: 'teal' | 'attention' | 'verified'
  username: string
  password: string
  icon: typeof Stethoscope
  description: string
  permissions: string
}

const PRESET_PERSONAS: PersonaPreset[] = [
  {
    name: 'Dr. Sterling (Clinician)',
    roleLabel: 'CLINICIAN',
    roleVariant: 'teal',
    username: 'dr_sterling',
    password: 'ClinicianSec2026!',
    icon: Stethoscope,
    description: 'Chest radiology resident with diagnostic inference & PACS access.',
    permissions: 'View DICOM • Run AI Diagnostics • Grad-CAM • Scan Chat',
  },
  {
    name: 'Clara Vance (Privacy Officer)',
    roleLabel: 'PRIVACY OFFICER',
    roleVariant: 'attention',
    username: 'officer_clara',
    password: 'PrivacySec2026!',
    icon: ShieldAlert,
    description: 'Data protection officer authorized for DPDP Sec. 12 key destruction.',
    permissions: 'Execute Crypto-Shredding • Audit Logs • Key Lifecycle Review',
  },
  {
    name: 'Dev Admin (Security Admin)',
    roleLabel: 'SECURITY ADMIN',
    roleVariant: 'verified',
    username: 'admin_sec',
    password: 'AdminSec2026!',
    icon: Cpu,
    description: 'System administrator managing RBAC user registry & platform security.',
    permissions: 'User Management • RBAC Provisioning • System Telemetry',
  },
]

export function LoginPage() {
  const login = useWorkstationStore((s) => s.login)
  const isLoading = useWorkstationStore((s) => s.isLoading)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) {
      setErrorMsg('Please enter both username and password.')
      return
    }
    setErrorMsg(null)
    const success = await login(username.trim(), password)
    if (!success) {
      setErrorMsg('Invalid credentials. Check username and password.')
    }
  }

  const handleQuickLogin = async (preset: PersonaPreset) => {
    setUsername(preset.username)
    setPassword(preset.password)
    setErrorMsg(null)
    await login(preset.username, preset.password)
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-bg-canvas px-4 py-8 text-text-primary">
      <div className="w-full max-w-md space-y-6">
        {/* Academic Header Banner */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 rounded-full border border-border-subtle bg-bg-panel px-3 py-1 text-[11px] font-medium text-text-secondary">
            <span className="h-2 w-2 rounded-full bg-accent-verified animate-pulse" />
            <span>Zero-Trust Architecture • Information Security &amp; Cryptography</span>
          </div>

          <div className="flex items-center justify-center gap-2.5 pt-1">
            <span className="flex h-10 w-10 items-center justify-center rounded-[var(--control-radius)] border border-accent-brand-border bg-accent-brand-soft text-accent-brand shadow-xs">
              <ShieldCheck className="h-6 w-6" />
            </span>
            <div className="text-left">
              <h1 className="font-display text-xl font-bold tracking-tight text-text-primary">
                MedShield-AI
              </h1>
              <p className="text-xs text-text-muted">Zero-Trust Clinical AI & Crypto Workstation</p>
            </div>
          </div>
        </div>

        {/* Credentials Form Box */}
        <div className="rounded-[var(--panel-radius)] border border-border-strong bg-bg-panel p-6 shadow-xs">
          <div className="mb-5 flex items-center justify-between border-b border-border-subtle pb-3">
            <div>
              <h2 className="text-sm font-semibold text-text-primary">Clinical Portal Sign-In</h2>
              <p className="text-[11px] text-text-secondary">
                RFC 7519 JWT + Argon2id / bcrypt Authentication
              </p>
            </div>
            <Badge variant="teal">RBAC Enforced</Badge>
          </div>

          {errorMsg && (
            <div className="mb-4 rounded-[var(--control-radius)] border border-accent-critical-border bg-accent-critical-soft p-3 text-xs text-accent-critical">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="username"
                className="mb-1 block text-xs font-medium text-text-secondary"
              >
                Username or Staff Identifier
              </label>
              <div className="relative">
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. dr_sterling"
                  className="w-full rounded-[var(--control-radius)] border border-border-strong bg-bg-input px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-1 focus:ring-border-focus"
                  disabled={isLoading}
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1 block text-xs font-medium text-text-secondary"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full rounded-[var(--control-radius)] border border-border-strong bg-bg-input px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-1 focus:ring-border-focus"
                  disabled={isLoading}
                />
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full h-9 text-xs font-medium"
              disabled={isLoading}
            >
              {isLoading ? (
                <span className="flex items-center gap-1.5">
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-text-inverse border-t-transparent" />
                  Authenticating...
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  <KeyRound className="h-3.5 w-3.5" />
                  Sign In to Workstation
                </span>
              )}
            </Button>
          </form>
        </div>

        {/* Quick Viva Evaluator Persona Presets */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between px-1">
            <span className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
              Viva & Demonstration RBAC Personas
            </span>
            <span className="text-[10px] text-text-muted">Click to sign in instantly</span>
          </div>

          <div className="space-y-2">
            {PRESET_PERSONAS.map((preset) => {
              const Icon = preset.icon
              return (
                <button
                  key={preset.username}
                  type="button"
                  onClick={() => handleQuickLogin(preset)}
                  disabled={isLoading}
                  className="group flex w-full flex-col gap-1 rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel p-3 text-left transition-colors hover:border-border-strong hover:bg-bg-elevated focus-visible:outline-2 focus-visible:outline-border-focus disabled:opacity-50"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-[var(--control-radius)] bg-bg-elevated text-text-secondary group-hover:text-accent-brand">
                        <Icon className="h-3.5 w-3.5" />
                      </span>
                      <span className="text-xs font-semibold text-text-primary">
                        {preset.name}
                      </span>
                    </div>
                    <Badge variant={preset.roleVariant}>{preset.roleLabel}</Badge>
                  </div>
                  <p className="text-[11px] text-text-secondary pl-8">{preset.description}</p>
                  <div className="mt-1 flex items-center gap-1 pl-8 text-[10px] text-text-muted font-mono">
                    <Lock className="h-2.5 w-2.5" />
                    <span>Perms: {preset.permissions}</span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Footer Security Badges */}
        <div className="flex items-center justify-center gap-4 text-[11px] text-text-muted">
          <span className="inline-flex items-center gap-1">
            <UserCheck className="h-3 w-3 text-accent-verified" />
            Stateless JWT
          </span>
          <span>•</span>
          <span>AES-256-GCM Envelope</span>
          <span>•</span>
          <span>Diffie–Hellman MODP</span>
        </div>
      </div>
    </div>
  )
}

