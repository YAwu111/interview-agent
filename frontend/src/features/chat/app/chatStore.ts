import { create } from 'zustand'
import type { ChatMessage, ChatMode, ChatSession, SourceItem } from '@/shared/services/types'
import { chatApi } from '../services/chatApi'
import { readSseCursor } from '../services/sseClient'
import { t } from '@/shared/lib/locale/zh'
import { invalidateCache } from '@/shared/services/resilience'

interface ChatState {
  sessions: ChatSession[]
  activeSessionId: string | null
  /** 当前会话的消息 */
  messages: ChatMessage[]
  isStreaming: boolean
  /** 当前阶段（后端 status 事件驱动）：retrieving/answering/probing/finalizing */
  status: string | null
  error: string | null
  /** 无会话或空会话时，输入区选择的模式 */
  pendingMode: ChatMode
  loadSessions: () => Promise<void>
  createSession: (mode: ChatMode) => Promise<ChatSession>
  selectSession: (id: string) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  setPendingMode: (mode: ChatMode) => void
  sendMessage: (text: string) => Promise<void>
  stop: () => void
  appendDelta: (messageId: string, content: string) => void
  resetError: () => void
  endInterview: () => void
}

let seq = 0
const localId = () => `local-${++seq}`
let abortController: AbortController | null = null
let selectSeq = 0
let suppressAutoOpen = false

const errText = (e: unknown) => (e instanceof Error ? e.message : t.chat.streamError)

export const useChatStore = create<ChatState>()((set, get) => ({
  sessions: [],
  activeSessionId: null,
  messages: [],
  isStreaming: false,
  status: null,
  error: null,
  pendingMode: 'chat',

  loadSessions: async () => {
    try {
      const sessions = await chatApi.listSessions()
      set({ sessions, error: null })
      const { activeSessionId } = get()
      if (!activeSessionId && sessions[0]) await get().selectSession(sessions[0].id)
    } catch (e) {
      set({ error: errText(e) })
    }
  },

  createSession: async (mode) => {
    const s = await chatApi.createSession(mode)
    set((st) => ({ sessions: [s, ...st.sessions], activeSessionId: s.id, messages: [], error: null }))
    if (mode === 'interview' && !suppressAutoOpen) void get().sendMessage('开始面试')
    return s
  },

  selectSession: async (id) => {
    if (get().activeSessionId === id) return
    if (get().isStreaming) get().stop()
    const target = get().sessions.find((s) => s.id === id)
    const reqId = ++selectSeq
    try {
      const messages = await chatApi.getMessages(id)
      if (reqId !== selectSeq) return // 期间又选了别的会话
      set({
        activeSessionId: id,
        messages,
        error: null,
        ...(target ? { pendingMode: target.mode } : {}),
      })
      const streaming = messages.find((m) => m.role === 'assistant' && m.status === 'streaming')
      if (streaming) {
        void (async () => {
          const controller = new AbortController()
          abortController = controller
          set({ isStreaming: true, status: null })
          const lastEventId = readSseCursor(id, streaming.id)
          try {
            for await (const chunk of chatApi.resumeChat(id, streaming.id, lastEventId, {
              signal: controller.signal,
            })) {
              if (chunk.type === 'delta') get().appendDelta(streaming.id, chunk.content)
              else if (chunk.type === 'status') set({ status: chunk.stage })
              else if (chunk.type === 'sources') {
                set((st) => ({
                  messages: st.messages.map((m) =>
                    m.id === streaming.id ? { ...m, sources: chunk.items } : m,
                  ),
                }))
              } else if (chunk.type === 'error') {
                set((st) => ({
                  error: chunk.message,
                  messages: st.messages.map((m) =>
                    m.id === streaming.id ? { ...m, status: 'error' } : m,
                  ),
                }))
              }
            }
          } catch (e) {
            if (!controller.signal.aborted) {
              set((st) => ({
                error: errText(e),
                messages: st.messages.map((m) =>
                  m.id === streaming.id ? { ...m, status: 'error' } : m,
                ),
              }))
            }
          } finally {
            abortController = null
            invalidateCache(`GET:/chat/sessions/${id}/messages`)
            set((st) => ({
              isStreaming: false,
              status: null,
              messages: st.messages.map((m) =>
                m.id === streaming.id && m.status === 'streaming'
                  ? { ...m, status: 'done' }
                  : m,
              ),
            }))
          }
        })()
      }
    } catch (e) {
      if (reqId === selectSeq) set({ error: errText(e) })
    }
  },

  deleteSession: async (id) => {
    if (get().isStreaming && get().activeSessionId === id) get().stop()
    try {
      await chatApi.deleteSession(id)
    } catch (e) {
      set({ error: errText(e) })
      return
    }
    const sessions = get().sessions.filter((s) => s.id !== id)
    set({ sessions })
    if (get().activeSessionId === id) {
      set({ activeSessionId: null, messages: [] })
      if (sessions[0]) await get().selectSession(sessions[0].id)
    }
  },

  setPendingMode: (mode) => {
    set({ pendingMode: mode })
    const { activeSessionId, messages, sessions } = get()
    // 空会话直接换模式并同步后端；有消息的会话模式锁定（输入区按钮禁用）
    if (activeSessionId && messages.length === 0) {
      set({
        sessions: sessions.map((s) => (s.id === activeSessionId ? { ...s, mode } : s)),
      })
      void chatApi.updateSession(activeSessionId, { mode })
      if (mode === 'interview') void get().sendMessage('开始面试')
    }
  },

  sendMessage: async (text) => {
    const content = text.trim()
    if (!content || get().isStreaming) return

    let sessionId = get().activeSessionId
    if (!sessionId) {
      suppressAutoOpen = true
      try {
        sessionId = (await get().createSession(get().pendingMode)).id
      } catch (e) {
        set({ error: errText(e) })
        return
      } finally {
        suppressAutoOpen = false
      }
    }

    const now = Date.now()
    const userMsg: ChatMessage = {
      id: localId(),
      sessionId,
      role: 'user',
      content,
      status: 'done',
      createdAt: now,
    }
    const assistantMsg: ChatMessage = {
      id: localId(),
      sessionId,
      role: 'assistant',
      content: '',
      status: 'streaming',
      createdAt: now + 1,
    }
    set((st) => ({
      messages: [...st.messages, userMsg, assistantMsg],
      isStreaming: true,
      error: null,
      // 首条消息更新会话标题与排序
      sessions: st.sessions
        .map((s) =>
          s.id === sessionId && st.messages.length === 0
            ? { ...s, title: content.slice(0, 20), updatedAt: now }
            : s,
        )
        .sort((a, b) => b.updatedAt - a.updatedAt),
    }))

    abortController = new AbortController()
    try {
      const stream = chatApi.streamChat(sessionId, content, { signal: abortController.signal })
      for await (const chunk of stream) {
        if (chunk.type === 'delta') get().appendDelta(assistantMsg.id, chunk.content)
        else if (chunk.type === 'sources') {
          set((st) => ({
            messages: st.messages.map((m) =>
              m.id === assistantMsg.id ? { ...m, sources: chunk.items } : m,
            ),
          }))
        } else if (chunk.type === 'status') {
          set({ status: chunk.stage })
        } else if (chunk.type === 'error') {
          set((st) => ({
            error: chunk.message,
            messages: st.messages.map((m) =>
              m.id === assistantMsg.id ? { ...m, status: 'error' } : m,
            ),
          }))
        }
      }
    } catch (e) {
      if (!abortController.signal.aborted) {
        set((st) => ({
          error: e instanceof Error ? e.message : t.chat.streamError,
          messages: st.messages.map((m) =>
            m.id === assistantMsg.id ? { ...m, status: 'error' } : m,
          ),
        }))
      }
    } finally {
      abortController = null
      invalidateCache(`GET:/chat/sessions/${sessionId}/messages`)
      set((st) => ({
        isStreaming: false,
        status: null,
        messages: st.messages.map((m) =>
          m.id === assistantMsg.id && m.status === 'streaming' ? { ...m, status: 'done' } : m,
        ),
      }))
    }
  },

  stop: () => {
    abortController?.abort()
    const sid = get().activeSessionId
    if (sid) void chatApi.stop(sid)
  },

  appendDelta: (messageId, content) =>
    set((st) => ({
      messages: st.messages.map((m) =>
        m.id === messageId ? { ...m, content: m.content + content } : m,
      ),
    })),

  resetError: () => set({ error: null }),

  endInterview: () => {
    const { activeSessionId, isStreaming } = get()
    if (!activeSessionId || isStreaming) return
    const now = Date.now()
    const reportMsg: ChatMessage = {
      id: localId(),
      sessionId: activeSessionId,
      role: 'assistant',
      content: '',
      status: 'streaming',
      createdAt: now,
    }
    set((st) => ({ messages: [...st.messages, reportMsg], isStreaming: true, error: null }))
    const controller = new AbortController()
    abortController = controller
    void (async () => {
      try {
        const stream = chatApi.end(activeSessionId, { signal: controller.signal })
        for await (const chunk of stream) {
          if (chunk.type === 'delta') get().appendDelta(reportMsg.id, chunk.content)
          else if (chunk.type === 'status') set({ status: chunk.stage })
          else if (chunk.type === 'error') {
            set((st) => ({
              error: chunk.message,
              messages: st.messages.map((m) =>
                m.id === reportMsg.id ? { ...m, status: 'error' } : m,
              ),
            }))
          }
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          set((st) => ({
            error: errText(e),
            messages: st.messages.map((m) =>
              m.id === reportMsg.id ? { ...m, status: 'error' } : m,
            ),
          }))
        }
      } finally {
        abortController = null
        invalidateCache(`GET:/chat/sessions/${activeSessionId}/messages`)
        set((st) => ({
          isStreaming: false,
          status: null,
          messages: st.messages.map((m) =>
            m.id === reportMsg.id && m.status === 'streaming' ? { ...m, status: 'done' } : m,
          ),
          sessions: st.sessions.map((s) =>
            s.id === activeSessionId ? { ...s, mode: 'chat' as ChatMode } : s,
          ),
          pendingMode: 'chat',
        }))
      }
    })()
  },
}))

export type { SourceItem }
