/**
 * 认证桥：apiClient（axios）与 sseClient（fetch 流）共用的令牌读取、401 回调与刷新。
 * 由 auth 模块的 tokenService 在 main.tsx 注入，避免 shared 反向依赖 feature。
 */

type TokenProvider = () => string | null
type UnauthorizedHandler = () => void
/** 刷新成功返回新 accessToken；无 refreshToken 或刷新失败返回 null */
type RefreshHandler = () => Promise<string | null>

let tokenProvider: TokenProvider = () => null
let unauthorizedHandler: UnauthorizedHandler = () => {}
let refreshHandler: RefreshHandler = async () => null
let refreshing: Promise<string | null> | null = null

export function setAuthHandlers(token: TokenProvider, unauthorized: UnauthorizedHandler) {
  tokenProvider = token
  unauthorizedHandler = unauthorized
}

export function setRefreshHandler(handler: RefreshHandler) {
  refreshHandler = handler
}

export const getAuthToken = (): string | null => tokenProvider()
export const handleUnauthorized = (): void => unauthorizedHandler()

/** single-flight：并发 401 只触发一次刷新，共享同一个 Promise */
export function refreshAccessToken(): Promise<string | null> {
  refreshing ??= refreshHandler().finally(() => {
    refreshing = null
  })
  return refreshing
}
