import { getAuthToken, handleUnauthorized, refreshAccessToken } from '@/shared/services/authBridge'
import { createSSEParser } from '@/shared/services/sseParser'
import { ApiError } from '@/shared/services/apiClient'
import { backoffDelay } from '@/shared/services/resilience/retry'
import type { SSEChunk } from '@/shared/services/types'

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function persistCursor(sessionId: string, messageId: string, lastEventId: number): void {
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem(`sse:${sessionId}:${messageId}`, String(lastEventId))
  }
}

export function readSseCursor(sessionId: string, messageId: string): number {
  if (typeof sessionStorage === 'undefined') return 0
  const raw = sessionStorage.getItem(`sse:${sessionId}:${messageId}`)
  const value = raw === null ? 0 : Number(raw)
  return Number.isFinite(value) ? value : 0
}

function clearCursor(sessionId: string, messageId: string): void {
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.removeItem(`sse:${sessionId}:${messageId}`)
  }
}

async function httpPost(
  path: string,
  body: unknown,
  signal: AbortSignal,
  retried = false,
): Promise<Response> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const token = getAuthToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(`/api/v1${path}`, {
    method: 'POST',
    body: JSON.stringify(body),
    headers,
    signal,
  })
  if (res.status === 401) {
    if (!retried && (await refreshAccessToken())) return httpPost(path, body, signal, true)
    handleUnauthorized()
    throw new ApiError(401, '未登录或登录已过期')
  }
  if (!res.ok || !res.body) throw new ApiError(res.status, `请求失败 (${res.status})`)
  return res
}

async function httpResume(
  sessionId: string,
  messageId: string,
  lastEventId: number,
  signal: AbortSignal,
  retried = false,
): Promise<Response> {
  const headers = new Headers({ 'Last-Event-ID': String(lastEventId) })
  const token = getAuthToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(
    `/api/v1/chat/sessions/${sessionId}/messages/${messageId}/stream`,
    { method: 'GET', headers, signal },
  )
  if (res.status === 401) {
    if (!retried && (await refreshAccessToken()))
      return httpResume(sessionId, messageId, lastEventId, signal, true)
    handleUnauthorized()
    throw new ApiError(401, '未登录或登录已过期')
  }
  if (!res.ok || !res.body) throw new ApiError(res.status, `请求失败 (${res.status})`)
  return res
}

async function* runResumable(
  path: string,
  body: unknown,
  sessionId: string,
  signal: AbortSignal,
): AsyncIterable<SSEChunk> {
  let messageId: string | null = null
  let lastEventId = 0
  let resumes = 0
  let res = await httpPost(path, body, signal)

  for (;;) {
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    const parser = createSSEParser()
    let terminated = false
    let errored = false
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        for (const chunk of parser.feedText(decoder.decode(value, { stream: true }))) {
          if (chunk.type === 'meta') {
            messageId = chunk.messageId
            continue
          }
          if (chunk.eventId !== undefined) {
            lastEventId = Math.max(lastEventId, chunk.eventId)
            if (messageId) persistCursor(sessionId, messageId, lastEventId)
          }
          if (chunk.type === 'done' || chunk.type === 'error') terminated = true
          yield chunk
        }
        if (signal.aborted) return
      }
      for (const chunk of parser.flush()) {
        if (chunk.type === 'meta') {
          messageId = chunk.messageId
          continue
        }
        if (chunk.eventId !== undefined) {
          lastEventId = Math.max(lastEventId, chunk.eventId)
          if (messageId) persistCursor(sessionId, messageId, lastEventId)
        }
        if (chunk.type === 'done' || chunk.type === 'error') terminated = true
        yield chunk
      }
    } catch {
      if (signal.aborted) return
      errored = true
    } finally {
      reader.cancel().catch(() => {})
    }

    if (terminated && messageId) clearCursor(sessionId, messageId)
    if (!errored || terminated) return
    if (!messageId) throw new ApiError(0, '流中断且无法续传')
    if (++resumes > 8) throw new ApiError(0, '连接反复中断，请稍后重试')

    for (let attempt = 0; attempt < 8; attempt++) {
      try {
        res = await httpResume(sessionId, messageId, lastEventId, signal)
        break
      } catch (err) {
        if (signal.aborted) return
        if (attempt === 7) throw err
        await sleep(backoffDelay(attempt, 500, 8_000))
      }
    }
  }
}

export async function* sseChatStream(
  sessionId: string,
  text: string,
  signal: AbortSignal,
): AsyncIterable<SSEChunk> {
  yield* runResumable(`/chat/sessions/${sessionId}/stream`, { text }, sessionId, signal)
}

export async function* sseEndSession(
  sessionId: string,
  signal: AbortSignal,
): AsyncIterable<SSEChunk> {
  yield* runResumable(`/chat/sessions/${sessionId}/end`, {}, sessionId, signal)
}

export async function* sseResumeSession(
  sessionId: string,
  messageId: string,
  lastEventId: number,
  signal: AbortSignal,
): AsyncIterable<SSEChunk> {
  const res = await httpResume(sessionId, messageId, lastEventId, signal)
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  const parser = createSSEParser()
  let terminated = false
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      for (const chunk of parser.feedText(decoder.decode(value, { stream: true }))) {
        if (chunk.type === 'meta') continue
        if (chunk.type === 'done' || chunk.type === 'error') terminated = true
        yield chunk
      }
      if (signal.aborted) return
    }
    for (const chunk of parser.flush()) {
      if (chunk.type === 'meta') continue
      if (chunk.type === 'done' || chunk.type === 'error') terminated = true
      yield chunk
    }
    if (terminated) clearCursor(sessionId, messageId)
  } finally {
    reader.cancel().catch(() => {})
  }
}
