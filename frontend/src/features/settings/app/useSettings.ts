import { useEffect } from 'react'
import { useSettingsStore } from './settingsStore'

export function useSettings() {
  const profile = useSettingsStore((s) => s.profile)
  const preferences = useSettingsStore((s) => s.preferences)
  const load = useSettingsStore((s) => s.load)
  const updateProfile = useSettingsStore((s) => s.updateProfile)
  const changePassword = useSettingsStore((s) => s.changePassword)
  const updatePreferences = useSettingsStore((s) => s.updatePreferences)

  useEffect(() => {
    void load()
  }, [load])

  return { profile, preferences, updateProfile, changePassword, updatePreferences }
}
