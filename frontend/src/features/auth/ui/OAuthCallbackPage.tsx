import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../app/authStore'
import { t } from '@/shared/lib/locale/zh'

/** live 模式 OAuth 重定向落地页：?code=... 或 ?error=... */
export function OAuthCallbackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const oauthCallback = useAuthStore((s) => s.oauthCallback)
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true
    const code = params.get('code')
    const error = params.get('error')
    if (!code) {
      navigate('/login', { replace: true, state: error ? { error } : undefined })
      return
    }
    oauthCallback(code)
      .then(() => navigate('/', { replace: true }))
      .catch(() => navigate('/login', { replace: true, state: { error: '第三方登录失败' } }))
  }, [params, oauthCallback, navigate])

  return (
    <div className="flex min-h-svh items-center justify-center bg-background">
      <p className="text-sm text-muted-foreground">{t.auth.loggingIn}</p>
    </div>
  )
}
