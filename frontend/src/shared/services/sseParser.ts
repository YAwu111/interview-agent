import type { SSEChunk } from './types'

/**
 * 纯函数 SSE 解析器，无 I/O、可单测。
 * 线协议：每个事件为若干 `data: <json>` 行 + 一个空行收尾。
 * feedText 处理跨块半行；flush 在流结束/中断时调用，残余半行按中断丢弃。
 */
export function createSSEParser() {
  let buf = ''
  let dataLines: string[] = []
  let events: SSEChunk[] = []

  const dispatch = () => {
    if (dataLines.length === 0) return
    const raw = dataLines.join('\n')
    dataLines = []
    try {
      events.push(JSON.parse(raw) as SSEChunk)
    } catch {
      events.push({ type: 'error', message: 'SSE 数据解析失败' })
    }
  }

  return {
    feedText(text: string): SSEChunk[] {
      buf += text
      const lines = buf.split('\n')
      buf = lines.pop() ?? ''
      events = []
      for (const rawLine of lines) {
        const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine
        if (line === '') dispatch()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
        // event:/id:/注释行忽略
      }
      return events
    },
    /** 流关闭时倒出最后一个无空行收尾的事件；中断的残缺行丢弃 */
    flush(): SSEChunk[] {
      buf = ''
      events = []
      dispatch()
      return events
    },
  }
}

/** delta 拼装：把一串 chunk 里的 delta 内容按序拼成完整文本 */
export const concatDeltas = (chunks: SSEChunk[]): string =>
  chunks.flatMap((c) => (c.type === 'delta' ? [c.content] : [])).join('')
