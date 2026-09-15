import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { useSettings } from '../app/useSettings'
import { ProfileForm } from './ProfileForm'
import { AppearanceForm } from './AppearanceForm'
import { t } from '@/shared/lib/locale/zh'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <h2 className="mb-4 text-base font-medium">{title}</h2>
      {children}
    </section>
  )
}

function PasswordForm() {
  const { changePassword } = useSettings()
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await changePassword(oldPwd, newPwd)
      setOldPwd('')
      setNewPwd('')
      toast.success(t.settings.passwordChanged)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '')
    }
  }

  return (
    <form onSubmit={submit} className="flex max-w-sm flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="old-pwd">{t.settings.oldPassword}</Label>
        <Input
          id="old-pwd"
          type="password"
          autoComplete="current-password"
          value={oldPwd}
          onChange={(e) => setOldPwd(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="new-pwd">{t.settings.newPassword}</Label>
        <Input
          id="new-pwd"
          type="password"
          autoComplete="new-password"
          value={newPwd}
          onChange={(e) => setNewPwd(e.target.value)}
        />
      </div>
      <div>
        <Button type="submit" variant="secondary">
          {t.settings.changePassword}
        </Button>
      </div>
    </form>
  )
}

export function SettingsPage() {
  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-5 overflow-y-auto px-4 py-6">
      <h1 className="text-lg font-medium">{t.settings.title}</h1>
      <Section title={t.settings.profile}>
        <ProfileForm />
      </Section>
      <Section title={t.settings.account}>
        <PasswordForm />
      </Section>
      <Section title={t.settings.appearance}>
        <AppearanceForm />
      </Section>
      <Separator className="my-2" />
    </div>
  )
}
