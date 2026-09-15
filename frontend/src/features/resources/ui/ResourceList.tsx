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
import { useResources } from '../app/useResources'
import { t } from '@/shared/lib/locale/zh'

export function ResourceList() {
  const { resources, remove } = useResources()
  if (resources.length === 0) return null
  return (
    <div className="mt-6 flex flex-col divide-y">
      {resources.map((r) => (
        <div key={r.id} className="flex items-center gap-3 py-3">
          <span className="flex size-9 items-center justify-center rounded-md bg-primary/10">
            <FileText className="size-4 text-primary" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm">{r.name}</div>
            <div className="text-xs text-muted-foreground">
              {formatSize(r.size)} · {new Date(r.createdAt).toLocaleDateString('zh-CN')}
            </div>
          </div>
          <AlertDialog>
            <AlertDialogTrigger
              render={<Button variant="ghost" size="icon-sm" aria-label={t.common.delete} />}
            >
              <Trash2 className="size-3.5 text-muted-foreground" />
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t.common.delete}</AlertDialogTitle>
                <AlertDialogDescription>{t.resources.deleteConfirm}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t.common.cancel}</AlertDialogCancel>
                <AlertDialogAction onClick={() => void remove(r.id)}>
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
