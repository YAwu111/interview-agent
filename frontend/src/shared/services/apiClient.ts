import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { getAuthToken, handleUnauthorized, refreshAccessToken } from './authBridge.ts'

/** 归一后的 API 错误：message 取自 FastAPI 的 {detail} */
export class ApiError extends Error {
  status: number
  retryAfterMs?: number
  constructor(status: number, message: string, retryAfterMs?: number) {
    super(message)
    this.status = status
    this.retryAfterMs = retryAfterMs
  }
}

const toApiError = (err: unknown): ApiError => {
  if (err instanceof AxiosError) {
    const status = err.response?.status ?? 0
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : err.code === 'ERR_CANCELED'
          ? '请求已取消'
          : err.code === 'ECONNABORTED'
            ? '请求超时'
            : status
              ? `请求失败 (${status})`
              : '网络错误'
    return new ApiError(status, message, parseRetryAfter(err))
  }
  return new ApiError(0, err instanceof Error ? err.message : '未知错误')
}

function parseRetryAfter(err: AxiosError): number | undefined {
  const raw = err.response?.headers?.['retry-after']
  if (!raw) return undefined
  const seconds = Number(raw)
  if (Number.isFinite(seconds) && seconds >= 0) return Math.round(seconds * 1000)
  const date = Date.parse(raw)
  if (!Number.isNaN(date)) return Math.max(0, date - Date.now())
  return undefined
}

/** 401 时自动刷新并重试一次的标记；/auth/token 等刷新请求自身必须带上防循环 */
export type RetriableConfig = AxiosRequestConfig & { _skipAuthRetry?: boolean }

/** 工厂：单测可注入绝对 baseURL */
export function createClient(baseURL: string): AxiosInstance {
  const client = axios.create({ baseURL, timeout: 15_000 })

  client.interceptors.request.use((config) => {
    const token = getAuthToken()
    if (token) config.headers.set('Authorization', `Bearer ${token}`)
    return config
  })

  client.interceptors.response.use(
    (res) => res,
    async (err: unknown) => {
      if (err instanceof AxiosError && err.response?.status === 401) {
        const config = err.config as RetriableConfig | undefined
        if (config && !config._skipAuthRetry) {
          const token = await refreshAccessToken()
          if (token) return client({ ...config, _skipAuthRetry: true } as AxiosRequestConfig)
        }
        handleUnauthorized()
      }
      return Promise.reject(toApiError(err))
    },
  )

  return client
}

const client = createClient('/api/v1')

const unwrap = <T>(p: Promise<{ data: T }>) => p.then((r) => r.data)

export const apiGet = <T>(path: string, config?: AxiosRequestConfig) =>
  unwrap<T>(client.get(path, config))
export const apiPost = <T>(path: string, body?: unknown, config?: AxiosRequestConfig) =>
  unwrap<T>(client.post(path, body, config))
export const apiPatch = <T>(path: string, body?: unknown, config?: AxiosRequestConfig) =>
  unwrap<T>(client.patch(path, body, config))
/** 204/空响应返回 undefined */
export const apiDelete = (path: string, config?: AxiosRequestConfig) =>
  client.delete(path, config).then(() => undefined)

/** 表单上传：onUploadProgress 百分比，超时放宽 60s，可传 AbortSignal 取消 */
export const apiUpload = <T>(
  path: string,
  file: File,
  onProgress: (p: number) => void,
  signal?: AbortSignal,
) => {
  const form = new FormData()
  form.append('file', file)
  return unwrap<T>(
    client.post(path, form, {
      timeout: 60_000,
      signal,
      onUploadProgress: (e) => {
        if (e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    }),
  )
}
