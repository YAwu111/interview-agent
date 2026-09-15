import { useEffect } from 'react'
import { useKnowledgeStore } from './knowledgeStore'

/** 加载知识库；存在处理中文档时轮询刷新状态流转（mock 按时间推导状态） */
export function useKnowledge() {
  const bases = useKnowledgeStore((s) => s.bases)
  const activeBaseId = useKnowledgeStore((s) => s.activeBaseId)
  const documents = useKnowledgeStore((s) => s.documents)
  const uploads = useKnowledgeStore((s) => s.uploads)
  const load = useKnowledgeStore((s) => s.load)
  const selectBase = useKnowledgeStore((s) => s.selectBase)
  const create = useKnowledgeStore((s) => s.create)
  const upload = useKnowledgeStore((s) => s.upload)
  const remove = useKnowledgeStore((s) => s.remove)

  useEffect(() => {
    void load()
  }, [load])

  const processing = documents.some((d) => d.status === 'parsing' || d.status === 'indexing')
  useEffect(() => {
    if (!processing || !activeBaseId) return
    const timer = setInterval(() => void selectBase(activeBaseId), 1500)
    return () => clearInterval(timer)
  }, [processing, activeBaseId, selectBase])

  return { bases, activeBaseId, documents, uploads, load, selectBase, create, upload, remove }
}
