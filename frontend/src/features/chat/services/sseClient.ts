import { getAuthToken, handleUnauthorized, refreshAccessToken } from '@/shared/services/authBridge'
import { createSSEParser } from '@/shared/services/sseParser'
import { ApiError } from '@/shared/services/apiClient'
import type { SSEChunk } from '@/shared/services/types'

/** 聊天 SSE 流式请求：浏览器端流式走 fetch ReadableStream，token/401 与 axios 共用 authBridge */
async function httpStream(
  path: string,
  body: unknown,
  signal: AbortSignal,
  retried = false,
): Promise<Response> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const token = getAuthToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(`/api/v1${path}`, { method: 'POST', body: JSON.stringify(body), headers, signal })
  if (res.status === 401) {
    if (!retried && (await refreshAccessToken())) return httpStream(path, body, signal, true)
    handleUnauthorized()
    throw new ApiError(401, '未登录或登录已过期')
  }
  if (!res.ok || !res.body) throw new ApiError(res.status, `请求失败 (${res.status})`)
  return res
}

/** live 模式：把 SSE 字节流转成 AsyncIterable<SSEChunk>，支持 AbortSignal 中断 */
export async function* sseChatStream(
  sessionId: string,
  text: string,
  signal: AbortSignal,
): AsyncIterable<SSEChunk> {
  const res = await httpStream(`/chat/sessions/${sessionId}/stream`, { text }, signal)
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  const parser = createSSEParser()
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      for (const chunk of parser.feedText(decoder.decode(value, { stream: true }))) yield chunk
      if (signal.aborted) return
    }
    for (const chunk of parser.flush()) yield chunk
  } finally {
    reader.cancel().catch(() => {})
  }
}
