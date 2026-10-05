import type { Preferences, Profile, SettingsApi } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiPatch, apiPost } from '@/shared/services/apiClient'
import { idempotentWrite, invalidateCache, resilientGet } from '@/shared/services/resilience'
import { mockSettings } from '@/shared/services/mockAdapter'

const live: SettingsApi = {
  getProfile: () => resilientGet<Profile>('/settings/profile', undefined, { dedupe: true }),
  updateProfile: (p) =>
    idempotentWrite(
      (key) =>
        apiPatch<Profile>('/settings/profile', p, {
          headers: { 'Idempotency-Key': key },
        }),
      { method: 'PATCH', path: '/api/v1/settings/profile', body: p },
    ).then((profile) => {
      invalidateCache('GET:/settings/profile')
      return profile
    }),
  changePassword: (oldPassword, newPassword) =>
    apiPost<void>('/settings/password', { oldPassword, newPassword }),
  getPreferences: () =>
    resilientGet<Preferences>('/settings/preferences', undefined, { dedupe: true }),
  updatePreferences: (p) =>
    idempotentWrite(
      (key) =>
        apiPatch<Preferences>('/settings/preferences', p, {
          headers: { 'Idempotency-Key': key },
        }),
      { method: 'PATCH', path: '/api/v1/settings/preferences', body: p },
    ).then((prefs) => {
      invalidateCache('GET:/settings/preferences')
      return prefs
    }),
}

export const settingsApi: SettingsApi = API_MODE === 'mock' ? mockSettings : live
