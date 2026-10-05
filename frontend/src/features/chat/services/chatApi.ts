import type { ChatApi, ChatMessage, ChatSession } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiDelete, apiPatch, apiPost } from '@/shared/services/apiClient'
import { invalidateCache, resilientGet } from '@/shared/services/resilience'
import { mockChat } from '@/shared/services/mockAdapter'
import { sseChatStream, sseEndSession } from './sseClient'

const live: ChatApi = {
  listSessions: () => resilientGet<ChatSession[]>('/chat/sessions', undefined, { dedupe: true }),
  createSession: async (mode) => {
    const session = await apiPost<ChatSession>('/chat/sessions', { mode })
    invalidateCache('GET:/chat/sessions')
    return session
  },
  updateSession: async (id, patch) => {
    await apiPatch<void>(`/chat/sessions/${id}`, patch)
    invalidateCache('GET:/chat/sessions')
  },
  deleteSession: async (id) => {
    await apiDelete(`/chat/sessions/${id}`)
    invalidateCache('GET:/chat/sessions')
    invalidateCache(`GET:/chat/sessions/${id}/messages`)
  },
  getMessages: (sessionId) =>
    resilientGet<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`, undefined, { dedupe: true }),
  streamChat: (sessionId, text, { signal }) => sseChatStream(sessionId, text, signal),
  end: (sessionId, { signal }) => sseEndSession(sessionId, signal),
  stop: (sessionId) => apiPost<void>(`/chat/sessions/${sessionId}/stop`),
}

export const chatApi: ChatApi = API_MODE === 'mock' ? mockChat : live
