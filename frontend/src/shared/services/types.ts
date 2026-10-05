/** 服务层类型契约：前后端以本文件为准；mock/live 适配器都实现这些接口。 */

export interface User {
  id: string
  name: string
  email: string
  avatar?: string
}

export interface AuthResult {
  accessToken: string
  refreshToken: string
  /** access token 有效期（秒） */
  expiresIn: number
  user: User
}

export type OAuthProvider = 'github' | 'google'

export interface AuthApi {
  login(email: string, password: string): Promise<AuthResult>
  register(name: string, email: string, password: string): Promise<AuthResult>
  oauth(provider: OAuthProvider): Promise<AuthResult>
  /** OAuth 回调一次性 code 换令牌（POST /auth/token, grant_type=authorization_code） */
  exchangeCode(code: string): Promise<AuthResult>
  /** 轮换刷新（POST /auth/token, grant_type=refresh_token） */
  refresh(refreshToken: string): Promise<AuthResult>
  logout(refreshToken: string | null): Promise<void>
}

export type ChatMode = 'chat' | 'interview'

export interface ChatSession {
  id: string
  title: string
  mode: ChatMode
  createdAt: number
  updatedAt: number
}

export interface SourceItem {
  id: string
  title: string
  snippet: string
  baseName?: string
}

export interface ChatMessage {
  id: string
  sessionId: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceItem[]
  status: 'streaming' | 'done' | 'error'
  createdAt: number
}

export type SSEChunk =
  | { type: 'delta'; content: string }
  | { type: 'sources'; items: SourceItem[] }
  | { type: 'status'; stage: string; round?: number }
  | { type: 'done' }
  | { type: 'error'; message: string }

export interface StreamOptions {
  signal: AbortSignal
}

export interface ChatApi {
  listSessions(): Promise<ChatSession[]>
  createSession(mode: ChatMode): Promise<ChatSession>
  updateSession(id: string, patch: { mode?: ChatMode }): Promise<void>
  deleteSession(id: string): Promise<void>
  getMessages(sessionId: string): Promise<ChatMessage[]>
  streamChat(sessionId: string, text: string, opts: StreamOptions): AsyncIterable<SSEChunk>
  /** 结束面试：触发报告生成，SSE 流式返回报告 markdown */
  end(sessionId: string, opts: StreamOptions): AsyncIterable<SSEChunk>
  stop(sessionId: string): Promise<void>
}

export type DocStatus = 'parsing' | 'indexing' | 'ready' | 'failed'

export interface KnowledgeBase {
  id: string
  name: string
  docCount: number
  createdAt: number
}

export interface KnowledgeDocument {
  id: string
  baseId: string
  name: string
  size: number
  status: DocStatus
  createdAt: number
}

export type UploadProgress = (percent: number) => void

export interface KnowledgeApi {
  listBases(): Promise<KnowledgeBase[]>
  createBase(name: string): Promise<KnowledgeBase>
  listDocuments(baseId: string): Promise<KnowledgeDocument[]>
  uploadDocument(baseId: string, file: File, onProgress: UploadProgress): Promise<KnowledgeDocument>
  deleteDocument(id: string): Promise<void>
}

export interface ResourceItem {
  id: string
  name: string
  size: number
  type: string
  createdAt: number
}

export interface ResourceApi {
  list(): Promise<ResourceItem[]>
  upload(file: File, onProgress: UploadProgress): Promise<ResourceItem>
  delete(id: string): Promise<void>
}

export interface Profile {
  name: string
  email: string
  title: string
  bio: string
}

export interface Preferences {
  language: 'zh-CN'
  emailDigest: boolean
}

export interface SettingsApi {
  getProfile(): Promise<Profile>
  updateProfile(p: Partial<Profile>): Promise<Profile>
  changePassword(oldPassword: string, newPassword: string): Promise<void>
  getPreferences(): Promise<Preferences>
  updatePreferences(p: Partial<Preferences>): Promise<Preferences>
}
