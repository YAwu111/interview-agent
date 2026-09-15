import type { Preferences, Profile, SettingsApi } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiGet, apiPatch, apiPost } from '@/shared/services/apiClient'
import { mockSettings } from '@/shared/services/mockAdapter'

const live: SettingsApi = {
  getProfile: () => apiGet<Profile>('/settings/profile'),
  updateProfile: (p) => apiPatch<Profile>('/settings/profile', p),
  changePassword: (oldPassword, newPassword) =>
    apiPost<void>('/settings/password', { oldPassword, newPassword }),
  getPreferences: () => apiGet<Preferences>('/settings/preferences'),
  updatePreferences: (p) => apiPatch<Preferences>('/settings/preferences', p),
}

export const settingsApi: SettingsApi = API_MODE === 'mock' ? mockSettings : live
