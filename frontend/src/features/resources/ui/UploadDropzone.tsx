import { useRef, useState } from 'react'
import { UploadCloud } from 'lucide-react'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'
import { ALLOWED_FILE_EXTS, uploadErrorText } from '@/shared/lib/constants'
import { useResources } from '../app/useResources'
import { t } from '@/shared/lib/locale/zh'

/** 拖拽/点击上传区，含白名单与 20MB 校验、进度与错误态 */
export function UploadDropzone() {
  const { upload, uploads } = useResources()
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const tasks = Object.values(uploads)

  const pick = (files: FileList | null) => {
    if (!files) return
    for (const file of Array.from(files)) void upload(file)
  }

  return (
    <div>
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
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          pick(e.dataTransfer.files)
        }}
        className={cn(
          'flex w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-10 text-center transition-colors',
          dragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50',
        )}
      >
        <UploadCloud className="size-8 text-muted-foreground" />
        <span className="text-sm">{t.resources.dropHint}</span>
        <span className="text-xs text-muted-foreground">{t.resources.dropRule}</span>
      </button>

      {tasks.length > 0 && (
        <div className="mt-3 flex flex-col gap-2">
          {tasks.map((task) => (
            <div key={task.id} className="text-xs">
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
    </div>
  )
}
