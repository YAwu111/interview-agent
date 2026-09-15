import { useState } from 'react'
import { ChevronDown, BookOpen } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'
import type { SourceItem } from '@/shared/services/types'
import { t } from '@/shared/lib/locale/zh'

/** 消息内的「引用来源」折叠块 */
export function SourceCite({ sources }: { sources: SourceItem[] }) {
  const [open, setOpen] = useState(false)
  if (sources.length === 0) return null
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-2">
      <CollapsibleTrigger className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
        <BookOpen className="size-3.5" />
        {t.chat.sources} ({sources.length})
        <ChevronDown className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-1 flex flex-col gap-1.5">
        {sources.map((s) => (
          <div key={s.id} className="rounded-md border bg-muted/50 px-3 py-2 text-xs">
            <div className="font-medium text-foreground">
              {s.title}
              {s.baseName && <span className="ml-2 text-muted-foreground">{s.baseName}</span>}
            </div>
            <p className="mt-0.5 text-muted-foreground">{s.snippet}</p>
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  )
}
