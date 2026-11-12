import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { Upload } from 'lucide-react'
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
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload a DICOM, PNG or JPEG chest X-ray"
      onClick={() => inputRef.current?.click()}
      onKeyDown={handleKeyDown}
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragOver(true)
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      className={cn(
        'flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 rounded-[var(--control-radius)] border border-dashed px-4 transition-colors focus-visible:outline-2 focus-visible:outline-border-focus',
        compact ? 'py-2.5' : 'py-4',
        isDragOver
          ? 'border-accent-brand bg-accent-brand-soft'
          : 'border-border-strong bg-bg-panel hover:border-accent-brand'
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
      <Upload className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
      <span className="text-[13px] text-text-primary">
        Drop a DICOM, PNG or JPEG here, or <span className="font-medium text-accent-brand">browse</span>
      </span>
      {enableClipboardPaste && (
        <span className="text-xs text-text-muted">You can also paste an image with Ctrl+V.</span>
      )}
    </div>
  )
}
