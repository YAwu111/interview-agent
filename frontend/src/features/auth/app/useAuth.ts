import { useAuthStore } from './authStore'

export function useAuth() {
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.accessToken)
  const status = useAuthStore((s) => s.status)
  const error = useAuthStore((s) => s.error)
  const login = useAuthStore((s) => s.login)
  const register = useAuthStore((s) => s.register)
  const oauth = useAuthStore((s) => s.oauth)
  const logout = useAuthStore((s) => s.logout)
  return { user, token, status, error, login, register, oauth, logout }
}
