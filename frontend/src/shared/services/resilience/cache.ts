type Entry<T> = { value: T; expiresAt: number }

export class LruCache {
  private readonly maxEntries: number
  private readonly map = new Map<string, Entry<unknown>>()

  constructor(maxEntries: number = 50) {
    this.maxEntries = maxEntries
  }

  get<T>(key: string): { value: T; fresh: boolean } | undefined {
    const entry = this.map.get(key) as Entry<T> | undefined
    if (!entry) return undefined
    // LRU：命中即提到末尾
    this.map.delete(key)
    this.map.set(key, entry)
    return { value: entry.value, fresh: entry.expiresAt > Date.now() }
  }

  set<T>(key: string, value: T, ttlMs: number): void {
    if (this.map.has(key)) this.map.delete(key)
    this.map.set(key, { value, expiresAt: Date.now() + ttlMs })
    while (this.map.size > this.maxEntries) {
      const oldest = this.map.keys().next().value
      if (oldest === undefined) break
      this.map.delete(oldest)
    }
  }

  delete(key: string): void {
    this.map.delete(key)
  }

  deleteByPrefix(prefix: string): void {
    for (const key of this.map.keys()) {
      if (key.startsWith(prefix)) this.map.delete(key)
    }
  }

  get size(): number {
    return this.map.size
  }
}

export const getCache = new LruCache(50)
