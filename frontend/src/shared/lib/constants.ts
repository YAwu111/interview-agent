/** API 模式：mock | live。默认 mock，后端就绪后设 VITE_API_MODE=live。 */
import { t } from './locale/zh'

export const API_MODE: 'mock' | 'live' =
  import.meta.env.VITE_API_MODE === 'live' ? 'live' : 'mock'

export const MAX_FILE_SIZE = 20 * 1024 * 1024 // 20MB
export const ALLOWED_FILE_EXTS = ['.pdf', '.docx', '.txt', '.md'] as const

/** 前端上传校验（后端仍为准） */
export function validateUploadFile(file: File): { ok: true } | { ok: false; error: string } {
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!(ALLOWED_FILE_EXTS as readonly string[]).includes(ext)) {
    return { ok: false, error: 'invalidType' }
  }
  if (file.size > MAX_FILE_SIZE) return { ok: false, error: 'tooLarge' }
  return { ok: true }
}

export const formatSize = (bytes: number): string =>
  bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`

/** 上传错误码 → 文案；未知错误（live 自由文本）原样透出 */
export function uploadErrorText(error: string): string {
  if (error === 'invalidType') return t.resources.invalidType
  if (error === 'tooLarge') return t.resources.tooLarge
  return error
}
