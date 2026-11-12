import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  ChevronRight,
  Loader2,
  MessageSquareText,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

const QUICK_QUESTIONS = [
  'Explain this finding in simple terms',
  'What did the heatmap highlight?',
  'Next recommended clinical steps',
] as const

function formatTimestamp(ts: number): string {
  try {
    return new Date(ts).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

export function ScanChatDrawer() {
  const chatOpen = useWorkstationStore((s) => s.chatOpen)
  const setChatOpen = useWorkstationStore((s) => s.setChatOpen)
  const isChatSending = useWorkstationStore((s) => s.isChatSending)
  const chatMessagesByStudy = useWorkstationStore((s) => s.chatMessagesByStudy)
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const worklist = useWorkstationStore((s) => s.worklist)
  const askScanQuestion = useWorkstationStore((s) => s.askScanQuestion)

  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const isShredded = Boolean(
    activeStudy &&
      worklist.some(
        (w) =>
          w.anonymous_study_instance_uid === activeStudy.anonymous_study_instance_uid &&
          w.is_shredded
      )
  )

  const scanId = activeStudy?.anonymous_study_instance_uid
  const messages = scanId ? chatMessagesByStudy[scanId] ?? [] : []

  const topFinding = activeStudy?.ai_diagnostics.predictions[0]

  useEffect(() => {
    if (chatOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [chatOpen, messages.length, isChatSending])

  useEffect(() => {
    if (chatOpen && !isChatSending && !isShredded && activeStudy) {
      textareaRef.current?.focus()
    }
  }, [chatOpen, isChatSending, isShredded, activeStudy])

  const handleSend = () => {
    const trimmed = inputValue.trim()
    if (!trimmed || isChatSending || !activeStudy || isShredded) return
    setInputValue('')
    void askScanQuestion(trimmed)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      e.key === 'Enter' &&
      !e.shiftKey &&
      !e.ctrlKey &&
      !e.metaKey &&
      !e.nativeEvent.isComposing &&
      e.keyCode !== 229
    ) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleQuickQuestionClick = (question: string) => {
    if (isChatSending || !activeStudy || isShredded) return
    void askScanQuestion(question)
  }

  return (
    <Sheet open={chatOpen} onOpenChange={setChatOpen}>
      <SheetContent
        className="flex flex-col p-0 focus:outline-none"
        aria-describedby="scan-chat-drawer-desc"
      >
        {/* Drawer Header */}
        <SheetHeader className="flex flex-col gap-2.5 border-b border-border-subtle bg-bg-input p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <MessageSquareText
                className="h-4 w-4 text-accent-brand"
                aria-hidden="true"
              />
              <SheetTitle>Ask AI About This Scan</SheetTitle>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-text-muted hover:text-text-primary"
              onClick={() => setChatOpen(false)}
              aria-label="Close scan chat"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          <SheetDescription id="scan-chat-drawer-desc" className="sr-only">
            Zero-PII conversational scan assistant for clinical explanation and evidence exploration.
          </SheetDescription>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="teal" className="gap-1">
              <ShieldCheck className="h-3 w-3" aria-hidden="true" />
              <span>Zero-PII Verified</span>
            </Badge>

            {activeStudy && topFinding ? (
              <span className="font-mono text-[11px] text-text-secondary truncate max-w-[240px]">
                {topFinding.pathology} &middot;{' '}
                {(topFinding.probability * 100).toFixed(1)}% (&plusmn;
                {topFinding.epistemic_uncertainty.toFixed(3)})
              </span>
            ) : (
              <span className="font-mono text-[11px] text-text-muted">
                No scan selected
              </span>
            )}
          </div>
        </SheetHeader>

        {/* Persistent Amber Clinical Scope Disclaimer */}
        <div className="flex items-start gap-2 border-b border-accent-attention-border bg-accent-attention-soft px-4 py-2 text-[11px] leading-snug text-accent-attention">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>
            AI explanations reflect anonymized model outputs only and do not establish a
            clinical diagnosis.
          </span>
        </div>

        {/* Scrollable Conversation Thread */}
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto bg-bg-panel p-4">
          {messages.length === 0 ? (
            <div className="my-auto flex flex-col items-center justify-center space-y-4 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full border border-accent-brand-border bg-accent-brand-soft">
                <Sparkles className="h-6 w-6 text-accent-brand" aria-hidden="true" />
              </div>

              <div className="max-w-xs space-y-1">
                <h3 className="font-display text-sm font-semibold text-text-primary">
                  Evidence-Grounded Scan Assistant
                </h3>
                <p className="text-xs text-text-secondary">
                  Ask questions about the scrubbed radiograph, DenseNet-121 model
                  findings, or Grad-CAM spatial heatmaps. Zero DICOM metadata leaves the enclave.
                </p>
              </div>

              <div className="w-full space-y-2 pt-2">
                <p className="text-[11px] font-medium text-text-muted uppercase tracking-wider text-left">
                  Suggested Questions
                </p>
                <div className="flex flex-col gap-1.5">
                  {QUICK_QUESTIONS.map((question) => (
                    <button
                      key={question}
                      type="button"
                      disabled={!activeStudy || isShredded || isChatSending}
                      onClick={() => handleQuickQuestionClick(question)}
                      className={cn(
                        'flex items-center justify-between gap-2 rounded-full border border-border-strong bg-bg-canvas px-3.5 py-2 text-left text-xs font-medium text-text-primary transition-colors',
                        'hover:bg-bg-elevated hover:border-accent-brand-border',
                        'disabled:pointer-events-none disabled:opacity-50'
                      )}
                    >
                      <span className="truncate">{question}</span>
                      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-text-muted" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => {
                if (message.role === 'user') {
                  return (
                    <div
                      key={message.id}
                      className="ml-auto max-w-[85%] rounded-[var(--panel-radius)] border border-accent-brand-border bg-accent-brand-soft p-3 text-xs leading-relaxed text-text-primary"
                    >
                      <div className="whitespace-pre-wrap">{message.content}</div>
                      <div className="mt-1 text-right text-[10px] text-text-muted">
                        {formatTimestamp(message.timestamp)}
                      </div>
                    </div>
                  )
                }

                if (message.role === 'assistant') {
                  return (
                    <div
                      key={message.id}
                      className="mr-auto max-w-[92%] space-y-2 rounded-[var(--panel-radius)] border border-border-subtle bg-bg-canvas p-3 text-xs leading-relaxed text-text-primary"
                    >
                      <div className="whitespace-pre-wrap">{message.content}</div>

                      <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-border-subtle">
                        <Badge variant="neutral" className="text-[10px]">
                          Grounded: DenseNet-121
                        </Badge>
                        {message.provider_used && (
                          <Badge variant="info" className="text-[10px]">
                            {message.provider_used}
                          </Badge>
                        )}
                        <span className="ml-auto text-[10px] text-text-muted">
                          {formatTimestamp(message.timestamp)}
                        </span>
                      </div>

                      {message.grounded_findings &&
                        message.grounded_findings.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-0.5">
                            {message.grounded_findings.map((f, i) => (
                              <span
                                key={i}
                                className="rounded border border-border-subtle bg-bg-panel px-1.5 py-0.5 text-[10px] text-text-secondary"
                              >
                                {f}
                              </span>
                            ))}
                          </div>
                        )}
                    </div>
                  )
                }

                // System / Error notification
                return (
                  <div
                    key={message.id}
                    className={cn(
                      'flex items-start gap-2.5 rounded-[var(--panel-radius)] border p-3 text-xs leading-relaxed',
                      message.isError
                        ? 'border-accent-critical-border bg-accent-critical-soft text-accent-critical'
                        : 'border-border-subtle bg-bg-elevated text-text-secondary'
                    )}
                  >
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                    <div className="flex-1 space-y-1">
                      <p className="font-semibold">
                        {message.isError
                          ? 'Right-to-Erasure Notice (DPDP Sec. 12)'
                          : 'Notice'}
                      </p>
                      <p>{message.content}</p>
                    </div>
                  </div>
                )
              })}

              {isChatSending && (
                <div className="mr-auto flex items-center gap-2 rounded-[var(--panel-radius)] border border-border-subtle bg-bg-canvas px-3 py-2 text-xs text-text-muted">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-accent-brand" />
                  <span>Analyzing scan with Zero-PII model...</span>
                </div>
              )}
            </>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Question Shortcut Strip when thread has messages */}
        {messages.length > 0 && !isShredded && activeStudy && (
          <div className="flex items-center gap-1.5 overflow-x-auto border-t border-border-subtle bg-bg-panel px-3 py-1.5">
            {QUICK_QUESTIONS.map((question) => (
              <button
                key={question}
                type="button"
                disabled={isChatSending}
                onClick={() => handleQuickQuestionClick(question)}
                className="shrink-0 rounded-full border border-border-strong bg-bg-canvas px-2.5 py-1 text-[11px] font-medium text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors disabled:opacity-50"
              >
                {question}
              </button>
            ))}
          </div>
        )}

        {/* Composer Footer */}
        <div className="flex flex-col gap-2 border-t border-border-subtle bg-bg-input p-3">
          <div className="relative">
            <textarea
              ref={textareaRef}
              rows={2}
              maxLength={1500}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!activeStudy || isShredded || isChatSending}
              placeholder={
                !activeStudy
                  ? 'Upload or select a scan first...'
                  : isShredded
                    ? 'Study erased under DPDP Sec. 12'
                    : 'Ask about this scan... (Enter to send, Shift+Enter for new line)'
              }
              className={cn(
                'w-full resize-none rounded-[var(--control-radius)] border border-border-strong bg-bg-panel p-2.5 text-xs text-text-primary placeholder:text-text-muted focus-visible:outline-2 focus-visible:outline-border-focus',
                'disabled:cursor-not-allowed disabled:bg-bg-elevated disabled:opacity-60'
              )}
            />
          </div>

          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px] leading-tight text-text-muted">
              Do not enter patient names, DOBs, or MRNs. Accidental identifiers are
              stripped before model egress.
            </p>

            <Button
              variant="primary"
              size="sm"
              disabled={
                !inputValue.trim() || !activeStudy || isShredded || isChatSending
              }
              onClick={handleSend}
              className="shrink-0 gap-1.5"
            >
              <Send className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Send</span>
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
