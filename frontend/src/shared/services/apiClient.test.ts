import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http'
import { createClient, ApiError } from './apiClient.ts'
import { setAuthHandlers, setRefreshHandler } from './authBridge.ts'

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

test('{detail} 错误体归一为 ApiError.message', async () => {
  await withServer(
    (_req, res) => {
      res.writeHead(422, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ detail: '参数不合法' }))
    },
    async (base) => {
      const err = await createClient(base).get('/x').catch((e: unknown) => e)
      assert.ok(err instanceof ApiError)
      assert.equal(err.status, 422)
      assert.equal(err.message, '参数不合法')
    },
  )
})

test('401 触发 onUnauthorized 回调', async () => {
  let called = 0
  setAuthHandlers(() => null, () => called++)
  await withServer(
    (_req, res) => {
      res.writeHead(401).end(JSON.stringify({ detail: '登录已过期' }))
    },
    async (base) => {
      const err = await createClient(base).get('/x').catch((e: unknown) => e)
      assert.ok(err instanceof ApiError)
      assert.equal(err.status, 401)
      assert.equal(called, 1)
    },
  )
  setAuthHandlers(() => null, () => {})
})

test('204/空响应正常返回不解析 body', async () => {
  await withServer(
    (_req, res) => res.writeHead(204).end(),
    async (base) => {
      const res = await createClient(base).delete('/x')
      assert.ok(!res.data)
    },
  )
})

test('取消请求归为「请求已取消」', async () => {
  await withServer(
    (req, res) => {
      req.socket.on('close', () => res.end())
    },
    async (base) => {
      const controller = new AbortController()
      const p = createClient(base).get('/x', { signal: controller.signal })
      controller.abort()
      const err = await p.catch((e: unknown) => e)
      assert.ok(err instanceof ApiError)
      assert.equal(err.message, '请求已取消')
    },
  )
})

test('请求头自动带 Bearer', async () => {
  setAuthHandlers(() => 'tok-abc', () => {})
  await withServer(
    (req, res) => {
      assert.equal(req.headers.authorization, 'Bearer tok-abc')
      res.writeHead(200, { 'Content-Type': 'application/json' }).end('{"ok":true}')
    },
    async (base) => {
      const res = await createClient(base).get<{ ok: boolean }>('/x')
      assert.equal(res.data.ok, true)
    },
  )
  setAuthHandlers(() => null, () => {})
})

test('401 刷新成功后重试原请求一次', async () => {
  let token: string | null = 'old'
  let unauthorized = 0
  let refreshCalls = 0
  setAuthHandlers(() => token, () => unauthorized++)
  setRefreshHandler(async () => {
    refreshCalls++
    token = 'new'
    return token
  })
  let seen: string[] = []
  await withServer(
    (req, res) => {
      seen.push(String(req.headers.authorization))
      if (req.headers.authorization === 'Bearer new') {
        res.writeHead(200, { 'Content-Type': 'application/json' }).end('{"ok":true}')
      } else {
        res.writeHead(401).end(JSON.stringify({ detail: 'expired' }))
      }
    },
    async (base) => {
      const res = await createClient(base).get<{ ok: boolean }>('/x')
      assert.equal(res.data.ok, true)
    },
  )
  assert.deepEqual(seen, ['Bearer old', 'Bearer new'])
  assert.equal(refreshCalls, 1)
  assert.equal(unauthorized, 0)
  setAuthHandlers(() => null, () => {})
  setRefreshHandler(async () => null)
})

test('401 刷新失败（无 refreshToken）走 onUnauthorized，不重试', async () => {
  let unauthorized = 0
  setAuthHandlers(() => 'old', () => unauthorized++)
  setRefreshHandler(async () => null)
  let hits = 0
  await withServer(
    (_req, res) => {
      hits++
      res.writeHead(401).end(JSON.stringify({ detail: 'expired' }))
    },
    async (base) => {
      const err = await createClient(base).get('/x').catch((e: unknown) => e)
      assert.ok(err instanceof ApiError)
      assert.equal(err.status, 401)
    },
  )
  assert.equal(hits, 1)
  assert.equal(unauthorized, 1)
  setAuthHandlers(() => null, () => {})
})
