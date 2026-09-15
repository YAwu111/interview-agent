import { create } from 'zustand'
import type { Preferences, Profile } from '@/shared/services/types'
import { settingsApi } from '../services/settingsApi'

interface SettingsState {
  profile: Profile | null
  preferences: Preferences | null
  load: () => Promise<void>
  updateProfile: (p: Partial<Profile>) => Promise<void>
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>
  updatePreferences: (p: Partial<Preferences>) => Promise<void>
}

export const useSettingsStore = create<SettingsState>()((set, get) => ({
  profile: null,
  preferences: null,

  load: async () => {
    const [profile, preferences] = await Promise.all([
      settingsApi.getProfile(),
      settingsApi.getPreferences(),
    ])
    set({ profile, preferences })
  },

  updateProfile: async (p) => {
    const profile = await settingsApi.updateProfile({ ...get().profile, ...p })
    set({ profile })
  },

  changePassword: async (oldPassword, newPassword) => {
    await settingsApi.changePassword(oldPassword, newPassword)
  },

  updatePreferences: async (p) => {
    const preferences = await settingsApi.updatePreferences({ ...get().preferences, ...p })
    set({ preferences })
  },
}))
