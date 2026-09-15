import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { ALLOWED_FILE_EXTS, uploadErrorText } from '@/shared/lib/constants'
import { useKnowledge } from '../app/useKnowledge'
import { t } from '@/shared/lib/locale/zh'

/** 上传文档对话框：白名单/20MB 校验 + 进度条 + 错误态 */
export function UploadDialog() {
  const { upload, uploads } = useKnowledge()
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const tasks = Object.values(uploads)

  const pick = (files: FileList | null) => {
    if (!files) return
    for (const file of Array.from(files)) void upload(file)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <Upload /> {t.knowledge.upload}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.knowledge.upload}</DialogTitle>
          <DialogDescription>{t.resources.dropRule}</DialogDescription>
        </DialogHeader>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ALLOWED_FILE_EXTS.join(',')}
          className="hidden"
          onChange={(e) => {
            pick(e.target.files)
            e.target.value = ''
          }}
        />
        <Button variant="outline" className="h-24 w-full border-dashed" onClick={() => inputRef.current?.click()}>
          {t.resources.dropHint}
        </Button>
        {tasks.length > 0 && (
          <div className="flex flex-col gap-2">
            {tasks.map((task) => (
              <div key={task.name} className="text-xs">
                <div className="mb-1 flex justify-between">
                  <span className="truncate">{task.name}</span>
                  {task.error ? (
                    <span className="text-destructive">{uploadErrorText(task.error)}</span>
                  ) : (
                    <span className="text-muted-foreground">{task.percent}%</span>
                  )}
                </div>
                {!task.error && <Progress value={task.percent} />}
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
