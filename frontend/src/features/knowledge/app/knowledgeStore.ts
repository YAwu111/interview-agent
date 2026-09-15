import { create } from 'zustand'
import type { KnowledgeBase, KnowledgeDocument } from '@/shared/services/types'
import { validateUploadFile } from '@/shared/lib/constants'
import { knowledgeApi } from '../services/knowledgeApi'

interface UploadTask {
  name: string
  percent: number
  error?: string
}

interface KnowledgeState {
  bases: KnowledgeBase[]
  activeBaseId: string | null
  documents: KnowledgeDocument[]
  uploads: Record<string, UploadTask>
  load: () => Promise<void>
  selectBase: (id: string) => Promise<void>
  create: (name: string) => Promise<void>
  upload: (file: File) => Promise<void>
  remove: (id: string) => Promise<void>
}

export const useKnowledgeStore = create<KnowledgeState>()((set, get) => ({
  bases: [],
  activeBaseId: null,
  documents: [],
  uploads: {},

  load: async () => {
    const bases = await knowledgeApi.listBases()
    set({ bases })
    const active = get().activeBaseId
    if (!active && bases[0]) await get().selectBase(bases[0].id)
    else if (active) await get().selectBase(active)
  },

  selectBase: async (id) => {
    set({ activeBaseId: id })
    const documents = await knowledgeApi.listDocuments(id)
    if (get().activeBaseId === id) set({ documents })
  },

  create: async (name) => {
    const base = await knowledgeApi.createBase(name)
    set((st) => ({ bases: [...st.bases, base], activeBaseId: base.id, documents: [] }))
  },

  upload: async (file) => {
    const baseId = get().activeBaseId
    if (!baseId) return
    const v = validateUploadFile(file)
    if (!v.ok) {
      set((st) => ({
        uploads: { ...st.uploads, [file.name]: { name: file.name, percent: 0, error: v.error } },
      }))
      return
    }
    set((st) => ({ uploads: { ...st.uploads, [file.name]: { name: file.name, percent: 0 } } }))
    try {
      await knowledgeApi.uploadDocument(baseId, file, (percent) =>
        set((st) => ({ uploads: { ...st.uploads, [file.name]: { name: file.name, percent } } })),
      )
      set((st) => {
        const uploads = { ...st.uploads }
        delete uploads[file.name]
        return { uploads }
      })
      await get().selectBase(baseId)
    } catch (e) {
      set((st) => ({
        uploads: {
          ...st.uploads,
          [file.name]: { name: file.name, percent: 0, error: e instanceof Error ? e.message : 'failed' },
        },
      }))
    }
  },

  remove: async (id) => {
    await knowledgeApi.deleteDocument(id)
    const { activeBaseId } = get()
    if (activeBaseId) await get().selectBase(activeBaseId)
  },
}))
