import type { Preferences, Profile, SettingsApi } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiPatch, apiPost, ApiError } from '@/shared/services/apiClient'
import { idempotentWrite, invalidateCache, resilientGet } from '@/shared/services/resilience'
import { mockSettings } from '@/shared/services/mockAdapter'

const PW_KEY = 'ia-pw-change-key'

function passwordChangeKey(): string {
  if (typeof sessionStorage === 'undefined') return crypto.randomUUID()
  let key = sessionStorage.getItem(PW_KEY)
  if (!key) {
    key = crypto.randomUUID()
    sessionStorage.setItem(PW_KEY, key)
  }
  return key
}

function clearPasswordChangeKey(): void {
  if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem(PW_KEY)
}

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
      invalidateCache('GET:/settings/profile:')
      return profile
    }),
  changePassword: async (oldPassword, newPassword) => {
    try {
      await apiPost<void>(
        '/settings/password',
        { oldPassword, newPassword },
        { headers: { 'Idempotency-Key': passwordChangeKey() } },
      )
      clearPasswordChangeKey()
    } catch (e) {
      // 业务 4xx 说明本次 payload 不会成功：清 key，允许改正后用新 key 重试
      if (
        e instanceof ApiError &&
        e.status >= 400 &&
        e.status < 500 &&
        e.status !== 408 &&
        e.status !== 429
      ) {
        clearPasswordChangeKey()
      }
      throw e
    }
  },
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
      invalidateCache('GET:/settings/preferences:')
      return prefs
    }),
}

export const settingsApi: SettingsApi = API_MODE === 'mock' ? mockSettings : live
