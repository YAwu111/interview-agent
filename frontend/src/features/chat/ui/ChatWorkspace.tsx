import { useEffect, useState } from 'react'
import { PanelLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useChat } from '../app/useChat'
import { SessionSidebar } from './SessionSidebar'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { InterviewModeBar } from './InterviewModeBar'
import { t } from '@/shared/lib/locale/zh'

const STATUS_TEXT: Record<string, string> = {
  retrieving: t.chat.statusRetrieving,
  answering: t.chat.statusAnswering,
  probing: t.chat.statusProbing,
  finalizing: t.chat.statusFinalizing,
}

/** 聊天工作台：左会话栏 + 右聊天窗；窄屏会话栏可收起 */
export function ChatWorkspace() {
  const { messages, loadSessions, status } = useChat()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    void loadSessions()
  }, [loadSessions])

  return (
    <div className="flex h-full">
      <aside
        className={cn(
          'w-64 shrink-0 border-r',
          sidebarOpen ? 'block' : 'hidden',
          'lg:block',
        )}
      >
        <SessionSidebar />
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-10 shrink-0 items-center border-b px-2 lg:hidden">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="切换会话栏"
          >
            <PanelLeft />
          </Button>
        </div>
        <InterviewModeBar />
        <div className="min-h-0 flex-1">
          <MessageList messages={messages} />
        </div>
        {status && (
          <div className="flex shrink-0 items-center gap-2 border-t bg-muted/40 px-4 py-1.5 text-xs text-muted-foreground">
            <span className="size-1.5 animate-pulse rounded-full bg-primary" />
            {STATUS_TEXT[status] ?? status}
          </div>
        )}
        <MessageInput />
      </section>
    </div>
  )
}
