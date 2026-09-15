import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/features/auth/app/useAuth'

/** 受保护路由：无令牌跳 /login */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  const location = useLocation()
  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}
