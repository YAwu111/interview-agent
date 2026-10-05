import { useChatStore } from './chatStore'

export function useChat() {
  const sessions = useChatStore((s) => s.sessions)
  const activeSessionId = useChatStore((s) => s.activeSessionId)
  const messages = useChatStore((s) => s.messages)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const status = useChatStore((s) => s.status)
  const error = useChatStore((s) => s.error)
  const pendingMode = useChatStore((s) => s.pendingMode)
  const loadSessions = useChatStore((s) => s.loadSessions)
  const createSession = useChatStore((s) => s.createSession)
  const selectSession = useChatStore((s) => s.selectSession)
  const deleteSession = useChatStore((s) => s.deleteSession)
  const setPendingMode = useChatStore((s) => s.setPendingMode)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const stop = useChatStore((s) => s.stop)
  const endInterview = useChatStore((s) => s.endInterview)
  const resetError = useChatStore((s) => s.resetError)
  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null
  return {
    sessions,
    activeSessionId,
    activeSession,
    messages,
    isStreaming,
    status,
    error,
    pendingMode,
    loadSessions,
    createSession,
    selectSession,
    deleteSession,
    setPendingMode,
    sendMessage,
    stop,
    endInterview,
    resetError,
  }
}
