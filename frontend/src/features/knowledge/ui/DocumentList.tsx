import { FileText, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
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
import { formatSize } from '@/shared/lib/constants'
import { useKnowledge } from '../app/useKnowledge'
import { DocStatusBadge } from './DocStatusBadge'
import { t } from '@/shared/lib/locale/zh'

/** 当前知识库的文档列表 */
export function DocumentList() {
  const { documents, remove } = useKnowledge()
  if (documents.length === 0) {
    return <p className="py-12 text-center text-sm text-muted-foreground">{t.knowledge.empty}</p>
  }
  return (
    <div className="flex flex-col divide-y">
      {documents.map((d) => (
        <div key={d.id} className="flex items-center gap-3 px-1 py-3">
          <FileText className="size-4 shrink-0 text-muted-foreground" />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm">{d.name}</div>
            <div className="text-xs text-muted-foreground">
              {formatSize(d.size)} · {new Date(d.createdAt).toLocaleDateString('zh-CN')}
            </div>
          </div>
          <DocStatusBadge status={d.status} />
          <AlertDialog>
            <AlertDialogTrigger
              render={<Button variant="ghost" size="icon-sm" aria-label={t.common.delete} />}
            >
              <Trash2 className="size-3.5 text-muted-foreground" />
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t.common.delete}</AlertDialogTitle>
                <AlertDialogDescription>{t.knowledge.deleteConfirm}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t.common.cancel}</AlertDialogCancel>
                <AlertDialogAction onClick={() => void remove(d.id)}>
                  {t.common.confirm}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      ))}
    </div>
  )
}
