import { Moon, Sun } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/utils'
import { useSettings } from '../app/useSettings'
import { useThemeStore } from '../app/themeStore'
import { switchTheme } from '../app/switchTheme'
import { t } from '@/shared/lib/locale/zh'

/** 外观：主题切换（themeStore 联动）+ 偏好 */
export function AppearanceForm() {
  const { preferences, updatePreferences } = useSettings()
  const mode = useThemeStore((s) => s.mode)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <Label>{t.settings.theme}</Label>
        <div className="flex gap-2">
          {(['light', 'dark'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={(e) => switchTheme(m, e.currentTarget)}
              className={cn(
                'flex items-center gap-2 rounded-md border px-4 py-2.5 text-sm transition-colors',
                mode === m ? 'border-primary bg-primary/5 text-primary' : 'hover:bg-accent',
              )}
            >
              {m === 'light' ? <Sun className="size-4" /> : <Moon className="size-4" />}
              {m === 'light' ? t.settings.light : t.settings.dark}
            </button>
          ))}
        </div>
      </div>
      {preferences && (
        <div className="flex items-center justify-between">
          <Label htmlFor="digest">{t.settings.emailDigest}</Label>
          <Switch
            id="digest"
            checked={preferences.emailDigest}
            onCheckedChange={(v) => void updatePreferences({ emailDigest: v })}
          />
        </div>
      )}
    </div>
  )
}
