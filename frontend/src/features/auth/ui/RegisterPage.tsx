import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '../app/useAuth'
import { t } from '@/shared/lib/locale/zh'

export function RegisterPage() {
  const navigate = useNavigate()
  const { register, status, error } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const loading = status === 'loading'

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirm) {
      setLocalError('两次输入的密码不一致')
      return
    }
    setLocalError(null)
    try {
      await register(name, email, password)
      navigate('/', { replace: true })
    } catch {
      /* error 已在 store 中 */
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
          <p className="mt-1 text-sm text-muted-foreground">{t.auth.register}</p>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="name">{t.auth.nickname}</Label>
            <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
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
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirm">{t.auth.confirmPassword}</Label>
            <Input
              id="confirm"
              type="password"
              required
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          {(localError ?? error) && (
            <p className="text-sm text-destructive">{localError ?? error}</p>
          )}
          <Button type="submit" disabled={loading} className="mt-1 h-9">
            {t.auth.registerSubmit}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link to="/login" className="text-primary hover:underline">
            {t.auth.toLogin}
          </Link>
        </p>
      </div>
    </div>
  )
}
