import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { Profile } from '@/shared/services/types'
import { useSettings } from '../app/useSettings'
import { t } from '@/shared/lib/locale/zh'

function LoadedForm({ profile }: { profile: Profile }) {
  const { updateProfile } = useSettings()
  const [name, setName] = useState(profile.name)
  const [title, setTitle] = useState(profile.title)
  const [bio, setBio] = useState(profile.bio)
  const [saving, setSaving] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await updateProfile({ name, title, bio })
      toast.success(t.settings.saved)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="s-name">{t.settings.name}</Label>
        <Input id="s-name" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="s-title">{t.settings.jobTitle}</Label>
        <Input id="s-title" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="s-bio">{t.settings.bio}</Label>
        <Textarea id="s-bio" rows={3} value={bio} onChange={(e) => setBio(e.target.value)} />
      </div>
      <div>
        <Button type="submit" disabled={saving}>
          {t.settings.save}
        </Button>
      </div>
    </form>
  )
}

/** 个人资料表单：profile 加载完成后再挂载，避免 effect 回填 */
export function ProfileForm() {
  const { profile } = useSettings()
  if (!profile) return null
  return <LoadedForm profile={profile} />
}
