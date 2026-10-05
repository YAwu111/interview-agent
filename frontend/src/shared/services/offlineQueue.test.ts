import test from 'node:test'
import assert from 'node:assert/strict'
import { flushQueue, memoryStorage, type QueueItem } from './offlineQueue.ts'

const backoff0 = () => 0

const item = (partial: Partial<QueueItem>): QueueItem => ({
  id: '1',
  key: 'k1',
  method: 'POST',
  path: '/a',
  body: { x: 1 },
  createdAt: 1,
  ...partial,
})

test('FIFO 串行重放成功并移除队列', async () => {
  const storage = memoryStorage()
  await storage.put(item({ id: '1', path: '/a', createdAt: 1 }))
  await storage.put(item({ id: '2', path: '/b', method: 'DELETE', createdAt: 2 }))
  const seen: string[] = []
  const fetchImpl = (async (input: RequestInfo | URL) => {
    seen.push(String(input))
    return { status: 200 } as Response
  }) as unknown as typeof fetch

  const result = await flushQueue({ storage, fetchImpl, getToken: () => null, backoff: backoff0 })
  assert.deepEqual(seen, ['/a', '/b'])
  assert.equal(result.replayed, 2)
  assert.equal((await storage.list()).length, 0)
})

test('409 视为已执行成功，从队列移除', async () => {
  const storage = memoryStorage()
  await storage.put(item({}))
  const fetchImpl = (async () => ({ status: 409 }) as Response) as unknown as typeof fetch
  const result = await flushQueue({ storage, fetchImpl, getToken: () => null, backoff: backoff0 })
  assert.equal(result.replayed, 1)
  assert.equal((await storage.list()).length, 0)
})

test('瞬时网络错误按退避重试后成功', async () => {
  const storage = memoryStorage()
  await storage.put(item({}))
  let calls = 0
  const fetchImpl = (async () => {
    calls++
    if (calls < 3) throw new TypeError('network')
    return { status: 200 } as Response
  }) as unknown as typeof fetch
  const result = await flushQueue({ storage, fetchImpl, getToken: () => null, backoff: backoff0 })
  assert.equal(result.replayed, 1)
  assert.equal(calls, 3)
})

test('非可重试 4xx 停止队列并回调失败项', async () => {
  const storage = memoryStorage()
  await storage.put(item({ id: '1', path: '/a' }))
  await storage.put(item({ id: '2', path: '/b' }))
  const state: { failed: QueueItem | null } = { failed: null }
  const fetchImpl = (async (input: RequestInfo | URL) => {
    return { status: String(input) === '/a' ? 400 : 200 } as Response
  }) as unknown as typeof fetch
  const result = await flushQueue({
    storage,
    fetchImpl,
    getToken: () => null,
    backoff: backoff0,
    onError: (i) => (state.failed = i),
  })
  assert.equal(result.replayed, 0)
  assert.equal(result.failed?.id, '1')
  assert.equal(state.failed?.id, '1')
  assert.equal((await storage.list()).length, 2)
})
