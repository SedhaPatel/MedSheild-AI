import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { Clipboard, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function IngestionDropzone({
  enableClipboardPaste = true,
  compact = false,
}: {
  enableClipboardPaste?: boolean
  compact?: boolean
}) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const ingestFile = useWorkstationStore((s) => s.ingestFile)

  useEffect(() => {
    if (!enableClipboardPaste) return
    function onPaste(e: ClipboardEvent) {
      const target = e.target as HTMLElement | null
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          const blob = item.getAsFile()
          if (blob) {
            const ext = item.type.includes('jpeg') ? 'jpg' : 'png'
            const pasted = new File([blob], `clipboard_radiograph.${ext}`, {
              type: item.type,
            })
            void ingestFile(pasted)
            return
          }
        }
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [enableClipboardPaste, ingestFile])

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) {
      void ingestFile(dropped)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      inputRef.current?.click()
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold tracking-wide text-text-secondary uppercase">
          Upload Radiograph
        </span>
        {enableClipboardPaste && (
          <span className="inline-flex items-center gap-1 text-[10px] font-medium text-text-muted">
            <Clipboard className="h-3 w-3" aria-hidden="true" />
            <span>Ctrl+V supported</span>
          </span>
        )}
      </div>

      <div
        role="button"
        tabIndex={0}
        aria-label="Upload DICOM or radiograph scan"
        onClick={() => inputRef.current?.click()}
        onKeyDown={handleKeyDown}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragOver(true)
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        className={cn(
          'cursor-pointer rounded-[var(--panel-radius)] border-2 border-dashed border-border-strong bg-bg-panel text-center transition-colors focus-visible:outline-2 focus-visible:outline-border-focus active:scale-[0.99]',
          compact ? 'px-4 py-5' : 'px-5 py-7',
          isDragOver
            ? 'border-accent-brand bg-accent-brand-soft'
            : 'hover:border-accent-brand hover:bg-bg-input'
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".dcm,.png,.jpg,.jpeg"
          className="hidden"
          onChange={(e) => {
            const inputEl = e.currentTarget
            const file = inputEl.files?.[0]
            if (file) {
              void ingestFile(file).finally(() => {
                inputEl.value = ''
              })
            }
          }}
        />
        <div className="mx-auto mb-2.5 flex h-10 w-10 items-center justify-center rounded-full border border-accent-brand-border bg-accent-brand-soft text-accent-brand">
          <Upload className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="font-display text-xs font-semibold text-text-primary">
          Drop chest X-ray here or click to browse
        </div>
        <div className="mt-1 text-[11px] text-text-muted">
          DICOM Part 10 (.dcm), PNG, or JPEG &middot; Auto-scrubbed before AI
        </div>
      </div>
    </div>
  )
}
