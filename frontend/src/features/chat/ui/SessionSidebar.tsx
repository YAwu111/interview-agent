import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { cn } from '@/lib/utils'
import { useChat } from '../app/useChat'
import { t } from '@/shared/lib/locale/zh'

/** 左栏：新建会话 + 会话列表（切换/删除） */
export function SessionSidebar() {
  const { sessions, activeSessionId, pendingMode, createSession, selectSession, deleteSession } =
    useChat()

  return (
    <div className="flex h-full flex-col bg-sidebar">
      <div className="p-3">
        <Button
          className="w-full"
          variant="outline"
          onClick={() => void createSession(pendingMode).catch(() => {})}
        >
          <Plus /> {t.chat.newChat}
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-0.5 px-2 pb-3">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={cn(
                'group flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors',
                s.id === activeSessionId
                  ? 'bg-sidebar-accent font-medium text-foreground'
                  : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
              )}
              onClick={() => void selectSession(s.id)}
            >
              <span className="min-w-0 flex-1 truncate">{s.title}</span>
              {s.mode === 'interview' && (
                <Badge variant="secondary" className="shrink-0 text-[10px]">
                  {t.chat.modeInterview}
                </Badge>
              )}
              <AlertDialog>
                <AlertDialogTrigger
                  render={
                    <button
                      className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-destructive lg:hidden lg:group-hover:block"
                      aria-label={t.common.delete}
                      onClick={(e) => e.stopPropagation()}
                    />
                  }
                >
                  <Trash2 className="size-3.5" />
                </AlertDialogTrigger>
                <AlertDialogContent onClick={(e) => e.stopPropagation()}>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t.common.delete}</AlertDialogTitle>
                    <AlertDialogDescription>{t.chat.deleteConfirm}</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t.common.cancel}</AlertDialogCancel>
                    <AlertDialogAction onClick={() => void deleteSession(s.id)}>
                      {t.common.confirm}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
