import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { Upload } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

export function IngestionDropzone() {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const ingestFile = useWorkstationStore((s) => s.ingestFile)

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
      <div className="text-[11px] font-medium tracking-wide text-text-secondary">
        Ingest Study
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
          'cursor-pointer rounded-[var(--panel-radius)] border border-dashed border-border-strong bg-bg-input px-3 py-4 text-center transition-colors focus-visible:outline-2 focus-visible:outline-border-focus active:scale-[0.985]',
          isDragOver
            ? 'border-accent-info bg-accent-info/10'
            : 'hover:border-accent-info/60 hover:bg-bg-elevated/40'
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
        <Upload className="mx-auto mb-1.5 h-5 w-5 text-text-muted" aria-hidden="true" />
        <div className="text-xs font-medium text-text-primary">
          Drop scan or browse
        </div>
        <div className="mt-0.5 text-[11px] text-text-muted">.dcm, .png, .jpg</div>
      </div>
    </div>
  )
}

