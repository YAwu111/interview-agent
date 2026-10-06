import type { ChatApi, ChatMessage, ChatSession } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiDelete, apiPatch, apiPost } from '@/shared/services/apiClient'
import { idempotentWrite, invalidateCache, resilientGet } from '@/shared/services/resilience'
import { mockChat } from '@/shared/services/mockAdapter'
import { sseChatStream, sseEndSession, sseResumeSession } from './sseClient'

const live: ChatApi = {
  listSessions: () => resilientGet<ChatSession[]>('/chat/sessions', undefined, { dedupe: true }),
  createSession: (mode) =>
    idempotentWrite(
      (key) =>
        apiPost<ChatSession>('/chat/sessions', { mode }, {
          headers: { 'Idempotency-Key': key },
        }),
      { method: 'POST', path: '/api/v1/chat/sessions', body: { mode } },
    ).then((session) => {
      invalidateCache('GET:/chat/sessions:')
      return session
    }),
  updateSession: (id, patch) =>
    idempotentWrite(
      (key) =>
        apiPatch<void>(`/chat/sessions/${id}`, patch, {
          headers: { 'Idempotency-Key': key },
        }),
      { method: 'PATCH', path: `/api/v1/chat/sessions/${id}`, body: patch },
    ).then(() => invalidateCache('GET:/chat/sessions:')),
  deleteSession: (id) =>
    idempotentWrite(
      (key) =>
        apiDelete(`/chat/sessions/${id}`, { headers: { 'Idempotency-Key': key } }),
      { method: 'DELETE', path: `/api/v1/chat/sessions/${id}` },
    ).then(() => {
      invalidateCache('GET:/chat/sessions:')
      invalidateCache(`GET:/chat/sessions/${id}/messages:`)
    }),
  getMessages: (sessionId) =>
    resilientGet<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`, undefined, { dedupe: true }),
  streamChat: (sessionId, text, { signal }) => sseChatStream(sessionId, text, signal),
  resumeChat: (sessionId, messageId, lastEventId, { signal }) =>
    sseResumeSession(sessionId, messageId, lastEventId, signal),
  end: (sessionId, { signal }) => sseEndSession(sessionId, signal),
  stop: (sessionId) => apiPost<void>(`/chat/sessions/${sessionId}/stop`),
}

export const chatApi: ChatApi = API_MODE === 'mock' ? mockChat : live
