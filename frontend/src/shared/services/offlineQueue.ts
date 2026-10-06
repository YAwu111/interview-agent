import { backoffDelay, RETRIABLE_STATUSES } from './resilience/retry.ts'

export type QueueMethod = 'POST' | 'PATCH' | 'DELETE'

export type QueueItem = {
  id: string
  key: string
  method: QueueMethod
  path: string
  body?: unknown
  createdAt: number
  order?: number
}

export interface QueueStorage {
  list(): Promise<QueueItem[]>
  put(item: QueueItem): Promise<void>
  remove(id: string): Promise<void>
  clear(): Promise<void>
}

export const memoryStorage = (): QueueStorage => {
  const items = new Map<string, QueueItem>()
  return {
    async list() {
      return [...items.values()]
    },
    async put(item) {
      items.set(item.id, item)
    },
    async remove(id) {
      items.delete(id)
    },
    async clear() {
      items.clear()
    },
  }
}

const DB_NAME = 'interview-agent-offline'
const STORE = 'writes'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function withStore<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE, mode)
      const req = fn(tx.objectStore(STORE))
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
  } finally {
    db.close()
  }
}

export const indexedDbStorage: QueueStorage = {
  list: () => withStore<QueueItem[]>('readonly', (s) => s.getAll()),
  put: (item) => withStore('readwrite', (s) => s.put(item)).then(() => undefined),
  remove: (id) => withStore('readwrite', (s) => s.delete(id)).then(() => undefined),
  clear: () => withStore('readwrite', (s) => s.clear()).then(() => undefined),
}

export const defaultStorage: QueueStorage =
  typeof indexedDB !== 'undefined' ? indexedDbStorage : memoryStorage()

let orderSeq = 0

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function replayOnce(
  item: QueueItem,
  fetchImpl: typeof fetch,
  getToken: () => string | null,
  refreshToken: () => Promise<string | null>,
  backoff: (attempt: number) => number,
): Promise<boolean> {
  let token = getToken()
  let tokenRefreshed = false
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (item.key) headers['Idempotency-Key'] = item.key
      if (token) headers.Authorization = `Bearer ${token}`
      const res = await fetchImpl(item.path, {
        method: item.method,
        headers,
        body: item.body === undefined ? undefined : JSON.stringify(item.body),
      })
      if (res.status === 401 && !tokenRefreshed) {
        const next = await refreshToken()
        if (next) {
          token = next
          tokenRefreshed = true
          continue
        }
      }
      if ((res.status >= 200 && res.status < 300) || res.status === 409) return true
      if (!RETRIABLE_STATUSES.has(res.status)) return false
    } catch {
      // 网络错误：继续按退避重试
    }
    if (attempt < 4) await sleep(backoff(attempt))
  }
  return false
}

export type FlushResult = { replayed: number; failed: QueueItem[] }

export async function flushQueue(opts: {
  storage: QueueStorage
  fetchImpl?: typeof fetch
  getToken: () => string | null
  refreshToken?: () => Promise<string | null>
  onError?: (item: QueueItem) => void
  backoff?: (attempt: number) => number
}): Promise<FlushResult> {
  const fetchImpl = opts.fetchImpl ?? fetch
  const refreshToken = opts.refreshToken ?? (async () => null)
  const backoff = opts.backoff ?? ((attempt: number) => backoffDelay(attempt, 500, 8_000))
  const items = (await opts.storage.list()).sort(
    (a, b) => (a.order ?? 0) - (b.order ?? 0) || a.createdAt - b.createdAt,
  )
  let replayed = 0
  const failed: QueueItem[] = []
  for (const item of items) {
    const ok = await replayOnce(item, fetchImpl, opts.getToken, refreshToken, backoff)
    if (!ok) {
      await opts.storage.remove(item.id)
      failed.push(item)
      opts.onError?.(item)
      continue
    }
    await opts.storage.remove(item.id)
    replayed++
  }
  return { replayed, failed }
}

export function installOfflineQueue(opts: {
  storage: QueueStorage
  getToken: () => string | null
  refreshToken?: () => Promise<string | null>
  onError?: (item: QueueItem) => void
  onFlush?: (result: FlushResult) => void
}): { flush: () => Promise<FlushResult> } {
  const flush = () =>
    flushQueue({
      storage: opts.storage,
      getToken: opts.getToken,
      refreshToken: opts.refreshToken,
      onError: opts.onError,
    }).then((result) => {
      opts.onFlush?.(result)
      return result
    })
  if (typeof window !== 'undefined') {
    window.addEventListener('online', () => void flush())
  }
  void flush()
  return { flush }
}

export function enqueueWrite(item: QueueItem): Promise<void> {
  return defaultStorage.put({ ...item, order: ++orderSeq })
}
