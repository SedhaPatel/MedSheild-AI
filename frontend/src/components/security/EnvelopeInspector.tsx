import { useState } from 'react'
import { toast } from 'sonner'
import { Panel } from '@/components/layout/Panel'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

function Field({ label, aside, children }: { label: string; aside?: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-2.5">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-text-muted">{label}</span>
        {aside && <span className="text-text-muted">{aside}</span>}
      </div>
      <div className="mt-1">{children}</div>
    </div>
  )
}

export function EnvelopeInspector() {
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const [copied, setCopied] = useState(false)

  if (!activeStudy) return null
  const sec = activeStudy.security
  const entropy = sec.shannon_entropy_bits_per_byte

  function copyDigest() {
    void navigator.clipboard.writeText(sec.sha256_hash)
    setCopied(true)
    toast('SHA-256 copied')
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Panel title="Encrypted storage" aside="AES-256-GCM envelope">
      <div className="divide-y divide-border-subtle text-[13px]">
        <Field label="Size">{sec.storage_file_size_bytes.toLocaleString()} bytes</Field>
        <Field label="Ciphertext entropy" aside="random data ≈ 8.00">
          <span className="font-mono tabular-nums">{entropy.toFixed(4)}</span>
          <span className="text-text-muted"> bits/byte {entropy >= 7.99 ? '(consistent with encryption)' : '(lower than expected)'}</span>
        </Field>
        <Field label="SHA-256" aside={copied ? 'Copied' : undefined}>
          <button
            type="button"
            onClick={copyDigest}
            title="Copy to clipboard"
            className="w-full cursor-pointer text-left font-mono text-xs leading-snug break-all text-text-secondary hover:text-text-primary"
          >
            {sec.sha256_hash}
          </button>
        </Field>
        <Field label="Header (first 64 bytes)">
          <code className="block font-mono text-xs leading-snug break-all text-text-secondary">{sec.hex_preview_64b}</code>
        </Field>
      </div>
    </Panel>
  )
}
