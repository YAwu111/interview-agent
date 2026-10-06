import { useEffect, useRef } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { Sparkles } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { ChatMessage } from '@/shared/services/types'
import { SourceCite } from './SourceCite'
import { t } from '@/shared/lib/locale/zh'

/** 流式打字光标 */
function StreamingCursor() {
  const reduce = useReducedMotion()
  return (
    <motion.span
      className="ml-0.5 inline-block h-4 w-2 translate-y-0.5 rounded-[2px] bg-primary"
      animate={reduce ? undefined : { opacity: [1, 0.15, 1] }}
      transition={{ repeat: Infinity, duration: 1, ease: 'easeInOut' }}
    />
  )
}

function MessageRow({ message }: { message: ChatMessage }) {
  const reduce = useReducedMotion()
  const isUser = message.role === 'user'
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={isUser ? 'flex justify-end' : 'flex justify-start'}
    >
      {isUser ? (
        <div className="max-w-[75%] rounded-lg bg-primary px-3.5 py-2.5 text-sm whitespace-pre-wrap text-primary-foreground">
          {message.content}
        </div>
      ) : (
        <div className="flex max-w-[85%] gap-2.5">
          <span className="mt-1 flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Sparkles className="size-3.5" />
          </span>
          <div className="min-w-0">
            <div className="text-sm leading-relaxed whitespace-pre-wrap">
              {message.content}
              {message.status === 'streaming' && <StreamingCursor />}
            </div>
            {message.status === 'error' && (
              <p className="mt-1 text-xs text-destructive">{t.chat.streamError}</p>
            )}
            {message.sources && <SourceCite sources={message.sources} />}
          </div>
        </div>
      )}
    </motion.div>
  )
}

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const prevCount = useRef(messages.length)
  const lastLen = messages.length ? messages[messages.length - 1].content.length : 0

  useEffect(() => {
    const el = bottomRef.current
    if (!el) return
    const isNewMessage = messages.length !== prevCount.current
    prevCount.current = messages.length
    const rect = el.getBoundingClientRect()
    const nearBottom = rect.bottom <= window.innerHeight + 40
    if (isNewMessage || nearBottom) el.scrollIntoView({ block: 'end' })
  }, [messages.length, lastLen])

  if (messages.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <h2 className="text-lg font-medium">{t.chat.emptyTitle}</h2>
        <p className="max-w-md text-sm text-muted-foreground">{t.chat.emptyHint}</p>
      </div>
    )
  }

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-6">
        {messages.map((m) => (
          <MessageRow key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
