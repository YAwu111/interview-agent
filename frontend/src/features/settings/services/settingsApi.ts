import type { Preferences, Profile, SettingsApi } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiPatch, apiPost } from '@/shared/services/apiClient'
import { invalidateCache, resilientGet } from '@/shared/services/resilience'
import { mockSettings } from '@/shared/services/mockAdapter'

const live: SettingsApi = {
  getProfile: () => resilientGet<Profile>('/settings/profile', undefined, { dedupe: true }),
  updateProfile: async (p) => {
    const profile = await apiPatch<Profile>('/settings/profile', p)
    invalidateCache('GET:/settings/profile')
    return profile
  },
  changePassword: (oldPassword, newPassword) =>
    apiPost<void>('/settings/password', { oldPassword, newPassword }),
  getPreferences: () =>
    resilientGet<Preferences>('/settings/preferences', undefined, { dedupe: true }),
  updatePreferences: async (p) => {
    const prefs = await apiPatch<Preferences>('/settings/preferences', p)
    invalidateCache('GET:/settings/preferences')
    return prefs
  },
}

export const settingsApi: SettingsApi = API_MODE === 'mock' ? mockSettings : live
