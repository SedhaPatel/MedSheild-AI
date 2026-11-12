import { useState } from 'react'
import { Lock } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function EnvelopeInspector() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const [copied, setCopied] = useState(false)

  const entropy = activeStudy?.security.shannon_entropy_bits_per_byte
  const entropyPct = entropy ? Math.min(100, (entropy / 8.0) * 100) : 0
  const passed = Boolean(entropy && entropy >= 7.99)

  function copyDigest() {
    if (!activeStudy) return
    void navigator.clipboard.writeText(activeStudy.security.sha256_hash)
    setCopied(true)
    toast.info('SHA-256 digest copied')
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <section
      aria-label="AES-256-GCM Envelope Inspection"
      className="overflow-hidden rounded-[var(--panel-radius)] border border-border-subtle bg-bg-panel"
    >
      <div className="flex items-center justify-between border-b border-border-subtle bg-bg-input px-4 py-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-text-primary">
          <Lock className="h-4 w-4 text-accent-teal" aria-hidden="true" />
          <span>Envelope Storage</span>
        </div>
        <Badge variant="teal">FIPS 140-3</Badge>
      </div>

      <div className="divide-y divide-border-subtle px-3.5 py-2.5">
        {/* Shannon Entropy */}
        <div className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-medium text-text-secondary">
              Shannon Entropy
            </span>
            <Badge variant={passed ? 'verified' : 'neutral'}>
              {entropy ? (passed ? 'Randomness Passed' : 'Below 7.99') : 'Target >= 7.99'}
            </Badge>
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="font-mono text-base font-semibold text-text-primary tabular-nums">
              {entropy !== undefined ? entropy.toFixed(5) : '--'}
            </span>
            <span className="text-[11px] text-text-muted">/ 8.00 bits/byte</span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border-subtle">
            <div
              className="h-full rounded-full bg-accent-verified transition-all duration-300"
              style={{ width: `${entropyPct}%` }}
            />
          </div>
        </div>

        {/* SHA-256 Digest */}
        <div className="py-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-text-secondary">
              Ciphertext SHA-256
            </span>
            <span className="text-[11px] text-text-muted">
              {copied ? 'Copied' : 'Click to copy'}
            </span>
          </div>
          <button
            type="button"
            disabled={!activeStudy}
            onClick={copyDigest}
            className="mt-1.5 w-full cursor-pointer break-all rounded-[var(--control-radius)] border border-border-subtle bg-bg-input px-2 py-1.5 text-left font-mono text-[11px] leading-snug text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            {activeStudy ? activeStudy.security.sha256_hash : '--'}
          </button>
        </div>

        {/* Wire Header Hex */}
        <div className="pt-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-text-secondary">
              Wire Header (64 B)
            </span>
            <span className="font-mono text-[11px] text-text-muted tabular-nums">
              {activeStudy
                ? `${activeStudy.security.storage_file_size_bytes.toLocaleString()} B`
                : '-- B'}
            </span>
          </div>
          <div className="mt-1.5 break-all rounded-[var(--control-radius)] border border-border-subtle bg-bg-input px-2 py-1.5 font-mono text-[11px] leading-snug text-text-secondary">
            {activeStudy ? activeStudy.security.hex_preview_64b : '--'}
          </div>
        </div>
      </div>
    </section>
  )
}

