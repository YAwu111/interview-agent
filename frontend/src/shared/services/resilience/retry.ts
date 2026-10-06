import { ApiError } from '../apiClient.ts'

export type RetryPolicy = {
  maxAttempts?: number
  baseMs?: number
  maxMs?: number
  retryOn?: (err: unknown) => boolean
}

export const RETRIABLE_STATUSES = new Set([408, 429, 502, 503, 504])

export function isRetriable(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false
  if (RETRIABLE_STATUSES.has(err.status)) return true
  return err.status === 0 && (err.message === '网络错误' || err.message === '请求超时')
}

/** full jitter：sleep = random(0, min(maxMs, baseMs * 2^attempt)) */
export function backoffDelay(attempt: number, baseMs = 500, maxMs = 8_000): number {
  const cap = Math.min(maxMs, baseMs * 2 ** attempt)
  return Math.round(Math.random() * cap)
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function withRetry<T>(
  fn: () => Promise<T>,
  policy: RetryPolicy = {},
): Promise<T> {
  const maxAttempts = policy.maxAttempts ?? 3
  const retryOn = policy.retryOn ?? isRetriable

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (err) {
      if (attempt === maxAttempts - 1 || !retryOn(err)) throw err
      const jittered = backoffDelay(attempt, policy.baseMs, policy.maxMs)
      const retryAfter = err instanceof ApiError ? err.retryAfterMs ?? 0 : 0
      await sleep(Math.max(jittered, retryAfter))
    }
  }
  // 不可达：循环上方必然 return 或 throw
  throw new Error('unreachable')
}
