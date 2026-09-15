import type {
  AuthApi,
  AuthResult,
  ChatApi,
  ChatMessage,
  ChatMode,
  ChatSession,
  DocStatus,
  KnowledgeApi,
  KnowledgeBase,
  KnowledgeDocument,
  Profile,
  ResourceApi,
  ResourceItem,
  SSEChunk,
  SettingsApi,
  SourceItem,
  StreamOptions,
  User,
} from './types'
import { MAX_FILE_SIZE, validateUploadFile } from '../lib/constants'

/** 内存 fixtures + 模拟流式输出；VITE_API_MODE=mock 时由各模块 services 选用。 */

const latency = (ms = 250) => new Promise((r) => setTimeout(r, ms))
let seq = 0
const nid = () => `m-${++seq}`

const user: User = { id: 'u1', name: '求职者', email: 'me@example.com' }

const now = Date.now()
const sessions: ChatSession[] = [
  { id: 's1', title: '自我介绍怎么讲', mode: 'chat', createdAt: now - 86400_000, updatedAt: now - 3600_000 },
  { id: 's2', title: '前端模拟面试', mode: 'interview', createdAt: now - 43200_000, updatedAt: now - 1800_000 },
]
const messagesBySession: Record<string, ChatMessage[]> = {
  s1: [
    {
      id: 'm1',
      sessionId: 's1',
      role: 'user',
      content: '自我介绍应该讲多久？',
      status: 'done',
      createdAt: now - 3500_000,
    },
    {
      id: 'm2',
      sessionId: 's1',
      role: 'assistant',
      content:
        '建议控制在 60–90 秒。结构可以是：一句话定位 → 两段与岗位最相关的经历 → 一个量化成果收尾。避免复述简历全文。',
      sources: [
        { id: 'src1', title: '前端面经合集', snippet: '自我介绍 60–90 秒为宜，突出与岗位匹配的经历…', baseName: '面试知识库' },
      ],
      status: 'done',
      createdAt: now - 3490_000,
    },
  ],
  s2: [],
}

const bases: KnowledgeBase[] = [
  { id: 'b1', name: '面试知识库', docCount: 3, createdAt: now - 7 * 86400_000 },
]
const documents: KnowledgeDocument[] = [
  { id: 'd1', baseId: 'b1', name: '前端面经合集.md', size: 182_000, status: 'ready', createdAt: now - 6 * 86400_000 },
  { id: 'd2', baseId: 'b1', name: '系统设计笔记.pdf', size: 2_400_000, status: 'ready', createdAt: now - 5 * 86400_000 },
  { id: 'd3', baseId: 'b1', name: '行为面试题库.docx', size: 96_000, status: 'ready', createdAt: now - 4 * 86400_000 },
]

const resources: ResourceItem[] = [
  { id: 'r1', name: '简历-2026.pdf', size: 320_000, type: '.pdf', createdAt: now - 3 * 86400_000 },
  { id: 'r2', name: '项目复盘.md', size: 24_000, type: '.md', createdAt: now - 2 * 86400_000 },
]

let profile: Profile = { name: '求职者', email: 'me@example.com', title: '前端工程师', bio: '' }
let preferences = { language: 'zh-CN' as const, emailDigest: true }

const checkFile = (file: File) => {
  const v = validateUploadFile(file)
  if (!v.ok) {
    throw new Error(v.error === 'tooLarge' ? `文件超过 ${MAX_FILE_SIZE / 1024 / 1024}MB 上限` : '不支持的文件类型')
  }
}

const fakeUpload = async (file: File, onProgress: (p: number) => void) => {
  checkFile(file)
  for (let p = 10; p <= 100; p += 10) {
    await latency(60)
    onProgress(p)
  }
}

// 文档状态按上传后经过的时间推导，模拟 解析中 → 索引中 → 就绪 的流转
const docStatus = (createdAt: number): DocStatus => {
  const elapsed = Date.now() - createdAt
  if (elapsed < 2000) return 'parsing'
  if (elapsed < 4500) return 'indexing'
  return 'ready'
}

const mockAuthResult = (u: User): AuthResult => ({
  accessToken: `mock-token-${nid()}`,
  refreshToken: `mock-refresh-${nid()}`,
  expiresIn: 1800,
  user: u,
})

export const mockAuth: AuthApi = {
  async login(email, password) {
    await latency()
    if (!email || !password) throw new Error('请输入邮箱和密码')
    return mockAuthResult({ ...user, email })
  },
  async register(name, email, password) {
    await latency()
    if (!name || !email || !password) throw new Error('请填写完整信息')
    return mockAuthResult({ ...user, name, email })
  },
  async oauth() {
    await latency(400)
    return mockAuthResult(user)
  },
  async exchangeCode(code) {
    await latency()
    if (!code) throw new Error('授权码无效')
    return mockAuthResult(user)
  },
  async refresh(refreshToken) {
    await latency(120)
    if (!refreshToken) throw new Error('登录已过期')
    return mockAuthResult(user)
  },
  async logout() {
    await latency(80)
  },
}

const INTERVIEW_QUESTIONS = [
  '请先做一个 60 秒左右的自我介绍。',
  '讲一个你最有成就感的项目，你在其中具体负责什么？',
  '如果页面出现白屏，你的排查思路是什么？',
  '你如何理解浏览器的渲染流程？关键渲染路径有哪些优化点？',
  '最后，你有什么想问面试官的？',
]

const CHAT_REPLY =
  '这是一个值得拆解的问题。结合你的目标岗位，建议先明确考察点，再用「情境-行动-结果」组织回答；如果有量化数据，放在结尾强调。需要的话，我可以基于你的知识库继续追问。'

async function* mockStream(sessionId: string, text: string, opts: StreamOptions): AsyncIterable<SSEChunk> {
  const session = sessions.find((s) => s.id === sessionId)
  const msgs = (messagesBySession[sessionId] ??= [])
  // 持久化用户消息，轮次按会话内真实助手消息数推进
  msgs.push({ id: nid(), sessionId, role: 'user', content: text, status: 'done', createdAt: Date.now() })
  const isInterview = session?.mode === 'interview'
  const round = msgs.filter((m) => m.role === 'assistant').length

  let reply: string
  let sources: SourceItem[] | undefined
  if (isInterview) {
    const q = INTERVIEW_QUESTIONS[Math.min(round, INTERVIEW_QUESTIONS.length - 1)]
    reply = round === 0 ? q : `收到。${text.length > 30 ? '回答信息量不错。' : '可以更具体一些。'}下一题：${q}`
  } else {
    reply = CHAT_REPLY
    sources = [
      { id: nid(), title: '前端面经合集', snippet: '与岗位匹配的表达结构：情境-行动-结果…', baseName: '面试知识库' },
      { id: nid(), title: '行为面试题库', snippet: '量化成果放在结尾强调，更容易被记住…', baseName: '面试知识库' },
    ]
  }

  if (sources && !opts.signal.aborted) yield { type: 'sources', items: sources }
  let acc = ''
  for (const ch of reply.match(/.{1,3}/gsu) ?? []) {
    if (opts.signal.aborted) break
    await latency(40)
    acc += ch
    yield { type: 'delta', content: ch }
  }
  // 中断也落库部分内容，切回会话可见
  msgs.push({ id: nid(), sessionId, role: 'assistant', content: acc, sources, status: 'done', createdAt: Date.now() })
  if (session) session.updatedAt = Date.now()
  if (!opts.signal.aborted) yield { type: 'done' }
}

export const mockChat: ChatApi = {
  async listSessions() {
    await latency()
    return [...sessions].sort((a, b) => b.updatedAt - a.updatedAt)
  },
  async createSession(mode: ChatMode) {
    await latency(120)
    const s: ChatSession = {
      id: nid(),
      title: mode === 'interview' ? '新的模拟面试' : '新会话',
      mode,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    sessions.unshift(s)
    messagesBySession[s.id] = []
    return s
  },
  async deleteSession(id) {
    await latency(120)
    const i = sessions.findIndex((s) => s.id === id)
    if (i >= 0) sessions.splice(i, 1)
    delete messagesBySession[id]
  },
  async updateSession(id, patch) {
    await latency(80)
    const s = sessions.find((x) => x.id === id)
    if (s && patch.mode) s.mode = patch.mode
  },
  async getMessages(sessionId) {
    await latency(150)
    return [...(messagesBySession[sessionId] ?? [])]
  },
  streamChat: mockStream,
  async stop() {
    /* mock 由 AbortSignal 中断，无需服务端动作 */
  },
}

export const mockKnowledge: KnowledgeApi = {
  async listBases() {
    await latency()
    return bases.map((b) => ({ ...b, docCount: documents.filter((d) => d.baseId === b.id).length }))
  },
  async createBase(name) {
    await latency()
    const b: KnowledgeBase = { id: nid(), name, docCount: 0, createdAt: Date.now() }
    bases.push(b)
    return b
  },
  async listDocuments(baseId) {
    await latency(120)
    return documents
      .filter((d) => d.baseId === baseId)
      .map((d) => ({ ...d, status: d.status === 'ready' || d.status === 'failed' ? d.status : docStatus(d.createdAt) }))
  },
  async uploadDocument(baseId, file, onProgress) {
    await fakeUpload(file, onProgress)
    const doc: KnowledgeDocument = {
      id: nid(),
      baseId,
      name: file.name,
      size: file.size,
      status: 'parsing',
      createdAt: Date.now(),
    }
    documents.push(doc)
    return doc
  },
  async deleteDocument(id) {
    await latency(120)
    const i = documents.findIndex((d) => d.id === id)
    if (i >= 0) documents.splice(i, 1)
  },
}

export const mockResources: ResourceApi = {
  async list() {
    await latency()
    return [...resources]
  },
  async upload(file, onProgress) {
    await fakeUpload(file, onProgress)
    const item: ResourceItem = {
      id: nid(),
      name: file.name,
      size: file.size,
      type: file.name.slice(file.name.lastIndexOf('.')).toLowerCase(),
      createdAt: Date.now(),
    }
    resources.unshift(item)
    return item
  },
  async delete(id) {
    await latency(120)
    const i = resources.findIndex((r) => r.id === id)
    if (i >= 0) resources.splice(i, 1)
  },
}

export const mockSettings: SettingsApi = {
  async getProfile() {
    await latency(120)
    return { ...profile }
  },
  async updateProfile(p) {
    await latency()
    profile = { ...profile, ...p }
    return { ...profile }
  },
  async changePassword(oldPassword, newPassword) {
    await latency()
    if (!oldPassword || newPassword.length < 6) throw new Error('新密码至少 6 位，且需输入当前密码')
  },
  async getPreferences() {
    await latency(80)
    return { ...preferences }
  },
  async updatePreferences(p) {
    await latency(80)
    preferences = { ...preferences, ...p }
    return { ...preferences }
  },
}
