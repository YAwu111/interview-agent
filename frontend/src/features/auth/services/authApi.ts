import type { AuthApi, AuthResult, OAuthProvider, User } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiPost, type RetriableConfig } from '@/shared/services/apiClient'
import { mockAuth } from '@/shared/services/mockAdapter'

/** 后端鉴权响应（snake_case）→ 前端 AuthResult（camelCase） */
interface LiveAuthResponse {
  access_token: string
  refresh_token: string
  expires_in: number
  user: User
}

const toAuthResult = (r: LiveAuthResponse): AuthResult => ({
  accessToken: r.access_token,
  refreshToken: r.refresh_token,
  expiresIn: r.expires_in,
  user: r.user,
})

/** 刷新/换码请求自身 401 不再触发刷新重试，防循环 */
const SKIP_RETRY: RetriableConfig = { _skipAuthRetry: true }

const tokenGrant = (fields: Record<string, string>) =>
  apiPost<LiveAuthResponse>('/auth/token', new URLSearchParams(fields), SKIP_RETRY).then(toAuthResult)

const live: AuthApi = {
  login: (email, password) =>
    apiPost<LiveAuthResponse>('/auth/login', { email, password }).then(toAuthResult),
  register: (name, email, password) =>
    apiPost<LiveAuthResponse>('/auth/register', { name, email, password }).then(toAuthResult),
  // live 模式为整页跳转 OAuth；回调页拿到一次性 code 后走 exchangeCode
  oauth: (provider: OAuthProvider) => {
    window.location.assign(`/api/v1/auth/oauth/${provider}`)
    return new Promise<AuthResult>(() => {})
  },
  exchangeCode: (code) => tokenGrant({ grant_type: 'authorization_code', code }),
  refresh: (refreshToken) => tokenGrant({ grant_type: 'refresh_token', refresh_token: refreshToken }),
  logout: (refreshToken) =>
    refreshToken ? apiPost<void>('/auth/logout', { refresh_token: refreshToken }) : Promise.resolve(),
}

export const authApi: AuthApi = API_MODE === 'mock' ? mockAuth : live
