import { Button } from '@/components/ui/button'
import { useChat } from '../app/useChat'
import { t } from '@/shared/lib/locale/zh'

/** 模拟面试进行中的顶部条：轮次 + 结束 */
export function InterviewModeBar() {
  const { activeSession, messages, endInterview } = useChat()
  if (!activeSession || activeSession.mode !== 'interview') return null
  const turns = messages.filter(
    (m) =>
      m.role === 'assistant' &&
      m.status !== 'error' &&
      !m.content.startsWith('# 面试报告'),
  ).length
  const round = turns + 1
  return (
    <div className="flex shrink-0 items-center justify-between border-b bg-muted/60 px-4 py-2">
      <span className="text-xs font-medium text-primary">{t.chat.interviewRound(round)}</span>
      <Button size="xs" variant="outline" onClick={endInterview}>
        {t.chat.endInterview}
      </Button>
    </div>
  )
}
