import { setAuthHandlers, setRefreshHandler } from '@/shared/services/authBridge'
import { useAuthStore } from '../app/authStore'

/** 把请求层接到 authStore：读令牌 + 401 刷新（single-flight 在 authBridge）+ 彻底失败清令牌跳登录。main.tsx 调用一次。 */
export function initTokenService() {
  setAuthHandlers(
    () => useAuthStore.getState().accessToken,
    () => {
      useAuthStore.getState().logoutLocal()
      if (window.location.pathname !== '/login') window.location.assign('/login')
    },
  )
  setRefreshHandler(() => useAuthStore.getState().tryRefresh())
}
