import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { AlertCircle, Check, ChevronRight, Copy, Loader2, RotateCcw, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { describeScore, rankPredictions } from '@/lib/scores'
import {
  selectIsActiveStudyShredded,
  useWorkstationStore,
} from '@/stores/useWorkstationStore'

const QUICK_QUESTIONS = [
  'Explain the result in simple terms',
  'Where is the heatmap focused?',
  'How reliable is this result?',
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

function parseInlineFormatting(text: string): ReactNode[] {
  // Matches ***bold italic***, **bold**, *italic*, or `code`
  const tokenRegex = /(\*\*\*[^*]+?\*\*\*|\*\*[^*]+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)/g
  const parts = text.split(tokenRegex)

  return parts.map((part, index) => {
    if (!part) return null
    if (part.startsWith('***') && part.endsWith('***') && part.length > 6) {
      return (
        <strong key={index} className="font-semibold text-text-primary">
          <em className="italic">{part.slice(3, -3)}</em>
        </strong>
      )
    }
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return (
        <strong key={index} className="font-semibold text-text-primary">
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return (
        <em key={index} className="italic">
          {part.slice(1, -1)}
        </em>
      )
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code
          key={index}
          className="rounded border border-border-subtle bg-bg-panel px-1 py-0.5 font-mono text-[11px] text-text-primary"
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}

function FormattedMessage({ content }: { content: string }) {
  const lines = content.split('\n')
  const blocks: ReactNode[] = []
  let currentListItems: ReactNode[] = []
  let currentListOrdered = false

  const flushList = () => {
    if (currentListItems.length > 0) {
      const ListTag = currentListOrdered ? 'ol' : 'ul'
      blocks.push(
        <ListTag
          key={`list-${blocks.length}`}
          className={cn(
            'my-1.5 space-y-1 pl-5 marker:text-text-muted',
            currentListOrdered ? 'list-decimal' : 'list-disc'
          )}
        >
          {currentListItems}
        </ListTag>
      )
      currentListItems = []
    }
  }

  lines.forEach((line, lineIndex) => {
    const trimmed = line.trim()

    if (!trimmed) {
      flushList()
      return
    }

    const bulletMatch = trimmed.match(/^[-*]\s+(.*)$/)
    const orderedMatch = bulletMatch ? null : trimmed.match(/^\d+\.\s+(.*)$/)
    const listMatch = bulletMatch ?? orderedMatch
    if (listMatch) {
      const ordered = Boolean(orderedMatch)
      if (currentListItems.length > 0 && ordered !== currentListOrdered) flushList()
      currentListOrdered = ordered
      const itemContent = listMatch[1]
      currentListItems.push(
        <li key={`li-${lineIndex}`} className="leading-relaxed">
          {parseInlineFormatting(itemContent)}
        </li>
      )
      return
    }

    flushList()

    const headingMatch = trimmed.match(/^#{1,4}\s+(.*)$/)
    if (headingMatch) {
      blocks.push(
        <div
          key={`h-${lineIndex}`}
          className="mt-2 mb-1 font-semibold text-text-primary"
        >
          {parseInlineFormatting(headingMatch[1])}
        </div>
      )
      return
    }

    blocks.push(
      <p key={`p-${lineIndex}`} className="leading-relaxed">
        {parseInlineFormatting(trimmed)}
      </p>
    )
  })

  flushList()

  return <div className="space-y-1.5">{blocks}</div>
}

export function ScanChatDrawer() {
  const chatOpen = useWorkstationStore((s) => s.chatOpen)
  const setChatOpen = useWorkstationStore((s) => s.setChatOpen)
  const isChatSending = useWorkstationStore((s) => s.isChatSending)
  const chatMessagesByStudy = useWorkstationStore((s) => s.chatMessagesByStudy)
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const isShredded = useWorkstationStore(selectIsActiveStudyShredded)
  const askScanQuestion = useWorkstationStore((s) => s.askScanQuestion)
  const retryScanQuestion = useWorkstationStore((s) => s.retryScanQuestion)
  const clearScanChat = useWorkstationStore((s) => s.clearScanChat)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const latestMessageRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scanId = activeStudy?.anonymous_study_instance_uid
  const messages = scanId ? chatMessagesByStudy[scanId] ?? [] : []

  const topFinding = activeStudy ? rankPredictions(activeStudy.ai_diagnostics.predictions)[0] : undefined

  // Follow-up chips: the latest answer's own suggestions, or the defaults if there are none
  const lastMessage = messages[messages.length - 1]
  const followUps =
    lastMessage?.role === 'assistant' && lastMessage.suggested_questions?.length
      ? lastMessage.suggested_questions
      : QUICK_QUESTIONS

  const copyAnswer = (id: string, content: string) => {
    void navigator.clipboard
      .writeText(content.replace(/\*\*/g, ''))
      .then(() => {
        setCopiedId(id)
        setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1500)
      })
      .catch(() => undefined)
  }

  useEffect(() => {
    if (!chatOpen) return

    if (isChatSending) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    } else if (messages.length > 0) {
      latestMessageRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
        <SheetHeader className="flex flex-col gap-1 border-b border-border-subtle bg-bg-panel px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <SheetTitle>Ask about this scan</SheetTitle>
            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={isChatSending}
                  onClick={clearScanChat}
                  className="text-text-muted hover:text-text-primary"
                >
                  Clear
                </Button>
              )}
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
          </div>

          <SheetDescription id="scan-chat-drawer-desc" className="sr-only">
            Zero-PII conversational scan assistant for clinical explanation and evidence exploration.
          </SheetDescription>

          <p className="truncate text-xs text-text-muted">
            {activeStudy && topFinding
              ? `${activeStudy.file_name} · top finding ${topFinding.pathology}: ${describeScore(topFinding)}`
              : 'No study open'}
          </p>
        </SheetHeader>

        {/* Persistent Amber Clinical Scope Disclaimer */}
        <p className="border-b border-border-subtle bg-bg-canvas px-4 py-2 text-xs leading-snug text-text-secondary">
          Answers are generated from the model&apos;s scores and heatmap for this study. They are not a diagnosis.
        </p>

        {/* Scrollable Conversation Thread */}
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto bg-bg-panel p-4 scroll-pt-4">
          {messages.length === 0 ? (
            <div className="space-y-3">
              <p className="text-[13px] text-text-secondary">
                Ask about the model&apos;s findings or the heatmap for this study. Only the de-identified image and
                scores are used; DICOM metadata is never sent.
              </p>

              <div className="space-y-1.5">
                <p className="text-xs text-text-muted">Try asking</p>
                <div className="flex flex-col gap-1.5">
                  {QUICK_QUESTIONS.map((question) => (
                    <button
                      key={question}
                      type="button"
                      disabled={!activeStudy || isShredded || isChatSending}
                      onClick={() => handleQuickQuestionClick(question)}
                      className={cn(
                        'flex w-full cursor-pointer items-center justify-between gap-2 rounded-[var(--control-radius)] border border-border-subtle bg-bg-panel px-3 py-2 text-left text-[13px] text-text-primary transition-colors',
                        'hover:border-border-strong hover:bg-bg-elevated',
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
              {messages.map((message, idx) => {
                const isLatest = idx === messages.length - 1

                if (message.role === 'user') {
                  return (
                    <div
                      key={message.id}
                      ref={isLatest ? latestMessageRef : undefined}
                      className="ml-auto max-w-[85%] rounded-[var(--panel-radius)] bg-bg-elevated px-3 py-2 text-[13px] leading-relaxed text-text-primary"
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
                      ref={isLatest ? latestMessageRef : undefined}
                      className="mr-auto max-w-full space-y-2 text-[13px] leading-relaxed text-text-primary"
                    >
                      {message.pii_redacted && (
                        <p className="text-xs text-text-muted">
                          Personal details in your question were removed before it was processed.
                        </p>
                      )}
                      <FormattedMessage content={message.content} />

                      <div className="flex items-center justify-between gap-2 border-t border-border-subtle pt-1.5 text-xs text-text-muted">
                        <span>
                          {message.provider_used === 'grounded-local-fallback'
                            ? 'Built-in assistant (no external model)'
                            : `Model: ${message.provider_used ?? 'unknown'}`}{' '}
                          &middot; {formatTimestamp(message.timestamp)}
                        </span>
                        <button
                          type="button"
                          onClick={() => copyAnswer(message.id, message.content)}
                          className="inline-flex cursor-pointer items-center gap-1 rounded-[var(--control-radius)] px-1.5 py-0.5 hover:bg-bg-elevated hover:text-text-primary"
                          aria-label="Copy answer"
                        >
                          {copiedId === message.id ? (
                            <><Check className="h-3 w-3" aria-hidden="true" /> Copied</>
                          ) : (
                            <><Copy className="h-3 w-3" aria-hidden="true" /> Copy</>
                          )}
                        </button>
                      </div>
                    </div>
                  )
                }

                // System / Error notification
                return (
                  <div
                    key={message.id}
                    ref={isLatest ? latestMessageRef : undefined}
                    className={cn(
                      'flex items-start gap-2.5 rounded-[var(--panel-radius)] border px-3 py-2 text-[13px] leading-relaxed',
                      message.isError
                        ? 'border-accent-critical-border bg-accent-critical-soft text-accent-critical'
                        : 'border-border-subtle bg-bg-elevated text-text-secondary'
                    )}
                  >
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                    <div className="flex-1 space-y-1">
                      <p className="font-semibold">
                        {message.title ?? (message.isError ? 'Request failed' : 'Notice')}
                      </p>
                      <p>{message.content}</p>
                      {message.retryQuestion && (
                        <Button
                          size="sm"
                          variant="destructive"
                          disabled={isChatSending}
                          onClick={() => {
                            void retryScanQuestion(message.id)
                          }}
                          className="mt-1"
                        >
                          <RotateCcw className="h-3 w-3" aria-hidden="true" />
                          Retry
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })}

              {isChatSending && (
                <div className="mr-auto flex items-center gap-2 text-[13px] text-text-muted">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Working…</span>
                </div>
              )}
            </>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Follow-up suggestions once the conversation has started */}
        {messages.length > 0 && !isShredded && activeStudy && (
          <div className="flex flex-wrap items-center gap-1.5 border-t border-border-subtle bg-bg-panel px-3 py-2">
            {followUps.map((question) => (
              <button
                key={question}
                type="button"
                disabled={isChatSending}
                onClick={() => handleQuickQuestionClick(question)}
                className="cursor-pointer rounded-[var(--control-radius)] border border-border-subtle bg-bg-panel px-2 py-1 text-left text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary disabled:opacity-50"
              >
                {question}
              </button>
            ))}
          </div>
        )}

        {/* Composer Footer */}
        <div className="flex flex-col gap-2 border-t border-border-subtle bg-bg-panel p-3">
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
                    ? 'This study was erased'
                    : 'Ask a question (Enter to send, Shift+Enter for a new line)'
              }
              className={cn(
                'w-full resize-none rounded-[var(--control-radius)] border border-border-strong bg-bg-panel p-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus-visible:outline-2 focus-visible:outline-border-focus',
                'disabled:cursor-not-allowed disabled:bg-bg-elevated disabled:opacity-60'
              )}
            />
          </div>

          <div className="flex items-center justify-between gap-2">
            <p className="text-xs leading-tight text-text-muted">
              Don&apos;t type names, dates of birth or record numbers. Common identifiers are removed before sending.
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
              Send
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
