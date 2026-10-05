import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http'
import { ApiError } from './apiClient.ts'
import {
  resilientGet,
  invalidateCache,
  isRetriable,
  backoffDelay,
} from './resilience/index.ts'
import { withRetry } from './resilience/retry.ts'
import { getCache } from './resilience/cache.ts'
import { withDedupe } from './resilience/dedupe.ts'

type Handler = (req: IncomingMessage, res: ServerResponse) => void

async function withServer(handler: Handler, fn: (base: string) => Promise<void>) {
  const server = createServer(handler)
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r))
  const { port } = server.address() as { port: number }
  try {
    await fn(`http://127.0.0.1:${port}`)
  } finally {
    server.close()
  }
}

test('isRetriable：只放行网络/超时/408/429/502/503/504', () => {
  assert.equal(isRetriable(new ApiError(503, 'x')), true)
  assert.equal(isRetriable(new ApiError(429, 'x')), true)
  assert.equal(isRetriable(new ApiError(0, '网络错误')), true)
  assert.equal(isRetriable(new ApiError(0, '请求超时')), true)
  assert.equal(isRetriable(new ApiError(401, 'x')), false)
  assert.equal(isRetriable(new ApiError(400, 'x')), false)
  assert.equal(isRetriable(new Error('x')), false)
})

test('backoffDelay 落在 [0, cap] 区间', () => {
  for (let i = 0; i < 50; i++) {
    const d = backoffDelay(1, 100, 200)
    assert.ok(d >= 0 && d <= 200)
  }
})

test('withRetry：瞬时错误重试后成功', async () => {
  let calls = 0
  const out = await withRetry(
    async () => {
      calls++
      if (calls < 3) throw new ApiError(0, '网络错误')
      return 'ok'
    },
    { maxAttempts: 3, baseMs: 1, maxMs: 2 },
  )
  assert.equal(out, 'ok')
  assert.equal(calls, 3)
})

test('withRetry：非可重试错误不重试', async () => {
  let calls = 0
  await assert.rejects(
    withRetry(async () => {
      calls++
      throw new ApiError(400, '参数错')
    }, { baseMs: 1, maxMs: 2 }),
  )
  assert.equal(calls, 1)
})

test('LruCache：TTL 过期、LRU 逐出与前缀失效', () => {
  invalidateCache()
  getCache.set('a:1', 'v1', 1000)
  getCache.set('a:2', 'v2', -1) // 立即过期
  assert.equal(getCache.get<string>('a:1')?.fresh, true)
  assert.equal(getCache.get<string>('a:2')?.fresh, false)
  getCache.set('b:1', 'v3', 1000)
  getCache.set('b:2', 'v4', 1000)
  assert.ok(getCache.size <= 50)
  invalidateCache('a:')
  assert.equal(getCache.get<string>('a:1'), undefined)
  assert.equal(getCache.get<string>('b:1')?.value, 'v3')
})

test('withDedupe：并发相同 key 只执行一次', async () => {
  let runs = 0
  const job = () =>
    new Promise<string>((resolve) => {
      runs++
      setTimeout(() => resolve('x'), 5)
    })
  const [a, b] = await Promise.all([withDedupe('k', job), withDedupe('k', job)])
  assert.equal(a, 'x')
  assert.equal(b, 'x')
  assert.equal(runs, 1)
})

test('resilientGet：新鲜缓存命中不重复请求，失效后重拉', async () => {
  invalidateCache()
  let hits = 0
  await withServer(
    (_req, res) => {
      hits++
      res.writeHead(200, { 'Content-Type': 'application/json' }).end('{"n":1}')
    },
    async (base) => {
      const cfg = { baseURL: base }
      const a = await resilientGet<{ n: number }>('/cache-hit', cfg, { cache: { ttlMs: 1000 } })
      const b = await resilientGet<{ n: number }>('/cache-hit', cfg, { cache: { ttlMs: 1000 } })
      assert.equal(a.n, 1)
      assert.equal(b.n, 1)
      assert.equal(hits, 1)
      invalidateCache('GET:/cache-hit')
      await resilientGet<{ n: number }>('/cache-hit', cfg, { cache: { ttlMs: 1000 } })
      assert.equal(hits, 2)
    },
  )
})

test('resilientGet：SWR 过期时先返回旧值并后台刷新', async () => {
  invalidateCache()
  let hits = 0
  await withServer(
    (_req, res) => {
      hits++
      res.writeHead(200, { 'Content-Type': 'application/json' }).end(`{"n":${hits}}`)
    },
    async (base) => {
      const cfg = { baseURL: base }
      const first = await resilientGet<{ n: number }>('/swr', cfg, { cache: { ttlMs: -1 } })
      assert.equal(first.n, 1)
      const stale = await resilientGet<{ n: number }>('/swr', cfg, {
        cache: { ttlMs: 1000, staleWhileRevalidate: true },
      })
      assert.equal(stale.n, 1)
      await new Promise((r) => setTimeout(r, 20))
      assert.ok(hits >= 2)
    },
  )
})

test('resilientGet：503 走重试，最终成功', async () => {
  invalidateCache()
  let hits = 0
  await withServer(
    (_req, res) => {
      hits++
      if (hits < 2) {
        res.writeHead(503).end(JSON.stringify({ detail: 'busy' }))
        return
      }
      res.writeHead(200, { 'Content-Type': 'application/json' }).end('{"ok":true}')
    },
    async (base) => {
      const out = await resilientGet<{ ok: boolean }>('/retry', { baseURL: base }, {
        retry: { maxAttempts: 3, baseMs: 1, maxMs: 2 },
      })
      assert.equal(out.ok, true)
      assert.equal(hits, 2)
    },
  )
})
