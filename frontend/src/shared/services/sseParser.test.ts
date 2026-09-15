import test from 'node:test'
import assert from 'node:assert/strict'
import { createSSEParser, concatDeltas } from './sseParser.ts'
import type { SSEChunk } from './types.ts'

test('delta 拼装：跨块半行也能按序拼接', () => {
  const p = createSSEParser()
  const chunks: SSEChunk[] = [
    ...p.feedText('data: {"type":"delta","content":"你好"}\n\ndata: {"type":"del'),
    ...p.feedText('ta","content":"，世界"}\n\n'),
    ...p.flush(),
  ]
  assert.equal(concatDeltas(chunks), '你好，世界')
})

test('sources / done 分支', () => {
  const p = createSSEParser()
  const src = { id: 's1', title: '面经', snippet: '…' }
  const out = p.feedText(
    `data: {"type":"sources","items":[${JSON.stringify(src)}]}\n\ndata: {"type":"done"}\n\n`,
  )
  assert.deepEqual(out[0], { type: 'sources', items: [src] })
  assert.deepEqual(out[1], { type: 'done' })
})

test('error 分支与坏 JSON', () => {
  const p = createSSEParser()
  const [err] = p.feedText('data: {"type":"error","message":"服务忙"}\n\n')
  assert.deepEqual(err, { type: 'error', message: '服务忙' })
  const [bad] = p.feedText('data: {oops}\n\n')
  assert.equal(bad.type, 'error')
})

test('中断：残余半行丢弃，已完整事件仍可从 flush 倒出', () => {
  const p = createSSEParser()
  p.feedText('data: {"type":"delta","content":"半截')
  assert.deepEqual(p.flush(), [])
  const p2 = createSSEParser()
  p2.feedText('data: {"type":"done"}\n\ndata: {"type":"delta","content":"x"}\n')
  assert.deepEqual(p2.flush(), [{ type: 'delta', content: 'x' }])
})
