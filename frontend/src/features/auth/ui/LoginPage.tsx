import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '../app/useAuth'
import { t } from '@/shared/lib/locale/zh'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const oauthError = (location.state as { error?: string } | null)?.error ?? null
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const { login, oauth, status, error } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const loading = status === 'loading'

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch {
      /* error 已在 store 中 */
    }
  }

  const oauthLogin = async (provider: 'github' | 'google') => {
    try {
      await oauth(provider)
      navigate(from, { replace: true })
    } catch {
      /* mock 模式下直接返回；live 为整页跳转 */
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex size-10 items-center justify-center rounded-lg bg-primary text-lg font-semibold text-primary-foreground">
            面
          </div>
          <h1 className="text-2xl font-medium">{t.app.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t.auth.login}</p>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">{t.auth.email}</Label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">{t.auth.password}</Label>
            <Input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {(error ?? oauthError) && (
            <p className="text-sm text-destructive">{error ?? oauthError}</p>
          )}
          <Button type="submit" disabled={loading} className="mt-1 h-9">
            {loading ? t.auth.loggingIn : t.auth.loginSubmit}
          </Button>
        </form>

        <div className="my-5 flex items-center gap-3">
          <Separator className="flex-1" />
          <span className="text-xs text-muted-foreground">{t.auth.oauthWith}</span>
          <Separator className="flex-1" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Button variant="outline" onClick={() => oauthLogin('github')} disabled={loading}>
            GitHub
          </Button>
          <Button variant="outline" onClick={() => oauthLogin('google')} disabled={loading}>
            Google
          </Button>
        </div>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link to="/register" className="text-primary hover:underline">
            {t.auth.toRegister}
          </Link>
        </p>
      </div>
    </div>
  )
}
