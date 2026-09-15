import type { ChatApi, ChatMessage, ChatSession } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiDelete, apiGet, apiPatch, apiPost } from '@/shared/services/apiClient'
import { mockChat } from '@/shared/services/mockAdapter'
import { sseChatStream } from './sseClient'

const live: ChatApi = {
  listSessions: () => apiGet<ChatSession[]>('/chat/sessions'),
  createSession: (mode) => apiPost<ChatSession>('/chat/sessions', { mode }),
  updateSession: (id, patch) => apiPatch<void>(`/chat/sessions/${id}`, patch),
  deleteSession: (id) => apiDelete(`/chat/sessions/${id}`),
  getMessages: (sessionId) => apiGet<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
  streamChat: (sessionId, text, { signal }) => sseChatStream(sessionId, text, signal),
  stop: (sessionId) => apiPost<void>(`/chat/sessions/${sessionId}/stop`),
}

export const chatApi: ChatApi = API_MODE === 'mock' ? mockChat : live
