import { Badge } from '@/components/ui/badge'
import type { DocStatus } from '@/shared/services/types'
import { t } from '@/shared/lib/locale/zh'

const STYLE: Record<DocStatus, string> = {
  parsing: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  indexing: 'bg-primary/10 text-primary',
  ready: 'bg-success/10 text-success',
  failed: 'bg-destructive/10 text-destructive',
}

export function DocStatusBadge({ status }: { status: DocStatus }) {
  return (
    <Badge variant="secondary" className={STYLE[status]}>
      {t.knowledge.status[status]}
    </Badge>
  )
}
