import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '../types'

// ─── Axios instance ────────────────────────────────────────────────────────
export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000,
})

// ─── Request interceptor: attach Bearer token ──────────────────────────────
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const raw = localStorage.getItem('access_token')
    const token = raw ? (JSON.parse(raw) as string) : null
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => Promise.reject(error),
)

// ─── Response interceptor: handle 401 → redirect to login ─────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      // Hard redirect so all React state is cleared
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

// ─── Multipart helper (file uploads) ──────────────────────────────────────
export const apiClientMultipart = axios.create({
  baseURL: '/api',
  timeout: 120_000, // longer timeout for file uploads
})

apiClientMultipart.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const raw = localStorage.getItem('access_token')
    const token = raw ? (JSON.parse(raw) as string) : null
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
      // Let browser set Content-Type with boundary for multipart
      delete config.headers['Content-Type']
    }
    return config
  },
  (error: AxiosError) => Promise.reject(error),
)

apiClientMultipart.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

// ─── Legacy typed API helpers (kept for backwards compatibility) ───────────
export const api = {
  get:    <T>(url: string, params?: Record<string, unknown>) =>
    apiClient.get<T>(url, { params }).then((r) => r.data),

  post:   <T>(url: string, data?: unknown) =>
    apiClient.post<T>(url, data).then((r) => r.data),

  put:    <T>(url: string, data?: unknown) =>
    apiClient.put<T>(url, data).then((r) => r.data),

  patch:  <T>(url: string, data?: unknown) =>
    apiClient.patch<T>(url, data).then((r) => r.data),

  delete: <T>(url: string) =>
    apiClient.delete<T>(url).then((r) => r.data),

  upload: <T>(url: string, formData: FormData) =>
    apiClientMultipart.post<T>(url, formData).then((r) => r.data),
}

export default apiClient
