import { useState } from 'react'
import { ArrowUp, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { ChatMode } from '@/shared/services/types'
import { useChat } from '../app/useChat'
import { t } from '@/shared/lib/locale/zh'

/** 输入区：模式切换 + 输入框 + 发送/停止 */
export function MessageInput() {
  const {
    activeSession,
    messages,
    isStreaming,
    pendingMode,
    setPendingMode,
    sendMessage,
    stop,
    error,
    resetError,
  } = useChat()
  const [text, setText] = useState('')

  // 会话已有内容时锁定其模式；否则跟随输入区选择
  const locked = !!activeSession && messages.length > 0
  const mode: ChatMode = locked ? activeSession.mode : pendingMode

  const submit = () => {
    const v = text.trim()
    if (!v || isStreaming) return
    setText('')
    void sendMessage(v)
  }

  return (
    <div className="shrink-0 border-t bg-background px-4 py-3">
      <div className="mx-auto max-w-3xl">
        {error && (
          <div className="mb-2 flex items-center justify-between rounded-md bg-destructive/10 px-3 py-1.5 text-xs text-destructive">
            <span>{error}</span>
            <button onClick={resetError} aria-label="关闭" className="ml-2 shrink-0 hover:opacity-70">
              ✕
            </button>
          </div>
        )}
        <div className="mb-2 flex items-center gap-1">
          {(['chat', 'interview'] as const).map((m) => (
            <button
              key={m}
              type="button"
              disabled={locked}
              onClick={() => setPendingMode(m)}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs transition-colors',
                mode === m
                  ? 'bg-primary/10 font-medium text-primary'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                locked && 'cursor-not-allowed opacity-60',
              )}
            >
              {m === 'chat' ? t.chat.modeChat : t.chat.modeInterview}
            </button>
          ))}
        </div>
        <div className="flex items-end gap-2">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                submit()
              }
            }}
            placeholder={t.chat.inputPlaceholder}
            rows={1}
            className="max-h-40 min-h-9 field-sizing-content flex-1 resize-none"
          />
          {isStreaming ? (
            <Button size="icon" variant="outline" onClick={stop} aria-label={t.chat.stop}>
              <Square />
            </Button>
          ) : (
            <Button size="icon" onClick={submit} disabled={!text.trim()} aria-label={t.chat.send}>
              <ArrowUp />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
