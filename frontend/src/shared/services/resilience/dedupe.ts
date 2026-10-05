const inflight = new Map<string, Promise<unknown>>()

export function withDedupe<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key)
  if (existing) return existing as Promise<T>
  const next = fn().finally(() => inflight.delete(key))
  inflight.set(key, next)
  return next
}
