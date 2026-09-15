import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useKnowledge } from '../app/useKnowledge'
import { DocumentList } from './DocumentList'
import { UploadDialog } from './UploadDialog'
import { t } from '@/shared/lib/locale/zh'

/** 知识库页：左库列表 + 右文档 */
export function KnowledgePage() {
  const { bases, activeBaseId, selectBase, create } = useKnowledge()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')

  return (
    <div className="mx-auto flex h-full max-w-5xl gap-6 px-4 py-6">
      <aside className="w-56 shrink-0">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium">{t.knowledge.title}</h2>
          <Button variant="ghost" size="icon-sm" onClick={() => setCreating((v) => !v)} aria-label={t.knowledge.newBase}>
            <Plus />
          </Button>
        </div>
        {creating && (
          <form
            className="mb-3 flex gap-1.5"
            onSubmit={(e) => {
              e.preventDefault()
              const v = name.trim()
              if (!v) return
              setName('')
              setCreating(false)
              void create(v)
            }}
          >
            <Input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t.knowledge.baseName}
            />
            <Button type="submit" size="sm" variant="secondary">
              {t.common.create}
            </Button>
          </form>
        )}
        <div className="flex flex-col gap-0.5">
          {bases.map((b) => (
            <button
              key={b.id}
              onClick={() => void selectBase(b.id)}
              className={cn(
                'rounded-md px-2.5 py-2 text-left text-sm transition-colors',
                b.id === activeBaseId
                  ? 'bg-accent font-medium'
                  : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
              )}
            >
              {b.name}
              <span className="ml-1.5 text-xs text-muted-foreground">{b.docCount}</span>
            </button>
          ))}
        </div>
      </aside>

      <section className="min-w-0 flex-1">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-lg font-medium">
            {bases.find((b) => b.id === activeBaseId)?.name ?? t.knowledge.title}
          </h1>
          {activeBaseId && <UploadDialog />}
        </div>
        <DocumentList />
      </section>
    </div>
  )
}
