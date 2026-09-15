import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AuthResult, OAuthProvider, User } from '@/shared/services/types'
import { authApi } from '../services/authApi'

export type AuthStatus = 'idle' | 'loading' | 'authed' | 'guest'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  /** access token 过期时间戳（ms），供主动刷新判断 */
  expiresAt: number | null
  status: AuthStatus
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  oauth: (provider: OAuthProvider) => Promise<void>
  /** live 模式：OAuth 回调一次性 code 换令牌 */
  oauthCallback: (code: string) => Promise<void>
  logout: () => Promise<void>
  logoutLocal: () => void
  /** 刷新令牌；成功返回新 accessToken，失败清登录态并返回 null */
  tryRefresh: () => Promise<string | null>
}

// ponytail: 令牌存 localStorage；接入真实后端后升级为 httpOnly Cookie + CSRF 防护
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => {
      const applyAuth = (r: AuthResult) =>
        set({
          accessToken: r.accessToken,
          refreshToken: r.refreshToken,
          expiresAt: Date.now() + r.expiresIn * 1000,
          user: r.user,
          status: 'authed',
        })
      const failTo = (fallback: string) => (e: unknown) => {
        set({ status: 'guest', error: e instanceof Error ? e.message : fallback })
        throw e
      }
      return {
        user: null,
        accessToken: null,
        refreshToken: null,
        expiresAt: null,
        status: 'guest',
        error: null,

        login: async (email, password) => {
          set({ status: 'loading', error: null })
          try {
            applyAuth(await authApi.login(email, password))
          } catch (e) {
            failTo('登录失败')(e)
          }
        },
        register: async (name, email, password) => {
          set({ status: 'loading', error: null })
          try {
            applyAuth(await authApi.register(name, email, password))
          } catch (e) {
            failTo('注册失败')(e)
          }
        },
        oauth: async (provider) => {
          set({ status: 'loading', error: null })
          try {
            applyAuth(await authApi.oauth(provider))
          } catch (e) {
            failTo('第三方登录失败')(e)
          }
        },
        oauthCallback: async (code) => {
          set({ status: 'loading', error: null })
          try {
            applyAuth(await authApi.exchangeCode(code))
          } catch (e) {
            failTo('第三方登录失败')(e)
          }
        },
        logout: async () => {
          await authApi.logout(get().refreshToken).catch(() => {})
          get().logoutLocal()
        },
        logoutLocal: () =>
          set({ user: null, accessToken: null, refreshToken: null, expiresAt: null, status: 'guest', error: null }),
        tryRefresh: async () => {
          const rt = get().refreshToken
          if (!rt) {
            set({ status: 'guest' })
            return null
          }
          try {
            const r = await authApi.refresh(rt)
            applyAuth(r)
            return r.accessToken
          } catch {
            get().logoutLocal()
            return null
          }
        },
      }
    },
    {
      name: 'ia-auth',
      partialize: (s) => ({
        user: s.user,
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
        expiresAt: s.expiresAt,
        status: s.status,
      }),
    },
  ),
)
