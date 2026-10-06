import type { AxiosRequestConfig } from 'axios'
import { apiGet, ApiError } from '../apiClient.ts'
import { enqueueWrite, type QueueItem } from '../offlineQueue.ts'
import { getCache } from './cache.ts'
import { withDedupe } from './dedupe.ts'
import { isRetriable, withRetry, type RetryPolicy } from './retry.ts'

export type CachePolicy = { ttlMs?: number; staleWhileRevalidate?: boolean }

export type ResilientGetOptions = {
  cache?: false | CachePolicy
  retry?: false | RetryPolicy
  dedupe?: boolean
}

const DEFAULT_TTL_MS = 30_000

function cacheKey(method: string, path: string, config?: AxiosRequestConfig): string {
  const params = config?.params ? JSON.stringify(config.params) : ''
  return `${method}:${path}:${params}`
}

export function invalidateCache(prefix = ''): void {
  getCache.deleteByPrefix(prefix)
}

export function resilientGet<T>(
  path: string,
  config?: AxiosRequestConfig,
  options: ResilientGetOptions = {},
): Promise<T> {
  const key = cacheKey('GET', path, config)

  const fetchFresh = () =>
    withRetry(
      () => apiGet<T>(path, config),
      options.retry === false ? { maxAttempts: 1, retryOn: () => false } : options.retry,
    )

  const fetchAndCache = () =>
    fetchFresh().then((value) => {
      if (options.cache !== false) {
        getCache.set(key, value, options.cache?.ttlMs ?? DEFAULT_TTL_MS)
      }
      return value
    })

  if (options.cache !== false) {
    const hit = getCache.get<T>(key)
    if (hit) {
      if (hit.fresh) return Promise.resolve(hit.value)
      if (options.cache?.staleWhileRevalidate) {
        void fetchAndCache().catch(() => {})
        return Promise.resolve(hit.value)
      }
    }
  }

  return options.dedupe ? withDedupe(key, fetchAndCache) : fetchAndCache()
}

export { isRetriable, backoffDelay, type RetryPolicy } from './retry.ts'

export async function idempotentWrite<T>(
  run: (key: string) => Promise<T>,
  descriptor: Omit<QueueItem, 'id' | 'key' | 'createdAt'>,
): Promise<T> {
  const key = globalThis.crypto.randomUUID()
  try {
    return await run(key)
  } catch (err) {
    if (isRetriable(err)) {
      try {
        await enqueueWrite({ ...descriptor, id: key, key, createdAt: Date.now() })
      } catch {
        throw err
      }
      throw new ApiError(0, '网络异常，操作已排队，联网后自动重试')
    }
    throw err
  }
}
