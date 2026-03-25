import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { User, Token } from '../api/types'

interface AuthState {
  user:      User | null
  isLoading: boolean
  error:     string | null
}

interface UseAuthReturn extends AuthState {
  login:    (email: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string) => Promise<void>
  logout:   () => void
  isAuthenticated: boolean
  clearError: () => void
}

// ─── Persist helpers ───────────────────────────────────────────────────────
function persistToken(token: string): void {
  localStorage.setItem('access_token', token)
}

function persistUser(user: User): void {
  localStorage.setItem('user', JSON.stringify(user))
}

function loadStoredUser(): User | null {
  try {
    const raw = localStorage.getItem('user')
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

// ─── Hook ─────────────────────────────────────────────────────────────────
export function useAuth(): UseAuthReturn {
  const navigate = useNavigate()

  const [state, setState] = useState<AuthState>({
    user:      loadStoredUser(),
    isLoading: false,
    error:     null,
  })

  // Re-hydrate user on mount (verify token is still valid)
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    setState((s) => ({ ...s, isLoading: true }))
    api
      .get<User>('/auth/me')
      .then((user) => {
        persistUser(user)
        setState({ user, isLoading: false, error: null })
      })
      .catch(() => {
        // Token invalid — clear storage; interceptor will redirect
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        setState({ user: null, isLoading: false, error: null })
      })
  }, [])

  // ── Login ────────────────────────────────────────────────────────────────
  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      setState((s) => ({ ...s, isLoading: true, error: null }))
      try {
        const data = await api.post<Token>('/auth/login', { email, password })
        persistToken(data.access_token)
        persistUser(data.user)
        setState({ user: data.user, isLoading: false, error: null })
        navigate('/dashboard')
      } catch (err: unknown) {
        const message = extractErrorMessage(err)
        setState((s) => ({ ...s, isLoading: false, error: message }))
        throw new Error(message)
      }
    },
    [navigate],
  )

  // ── Register ─────────────────────────────────────────────────────────────
  const register = useCallback(
    async (username: string, email: string, password: string): Promise<void> => {
      setState((s) => ({ ...s, isLoading: true, error: null }))
      try {
        const data = await api.post<Token>('/auth/register', {
          username,
          email,
          password,
        })
        persistToken(data.access_token)
        persistUser(data.user)
        setState({ user: data.user, isLoading: false, error: null })
        navigate('/dashboard')
      } catch (err: unknown) {
        const message = extractErrorMessage(err)
        setState((s) => ({ ...s, isLoading: false, error: message }))
        throw new Error(message)
      }
    },
    [navigate],
  )

  // ── Logout ────────────────────────────────────────────────────────────────
  const logout = useCallback((): void => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    setState({ user: null, isLoading: false, error: null })
    navigate('/login')
  }, [navigate])

  const clearError = useCallback((): void => {
    setState((s) => ({ ...s, error: null }))
  }, [])

  return {
    ...state,
    isAuthenticated: state.user !== null,
    login,
    register,
    logout,
    clearError,
  }
}

// ─── Utility ───────────────────────────────────────────────────────────────
function extractErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as { response?: { data?: { detail?: string }; status?: number } }
    if (axiosErr.response?.data?.detail) return axiosErr.response.data.detail
    if (axiosErr.response?.status === 401) return 'Invalid credentials.'
    if (axiosErr.response?.status === 422) return 'Validation error. Check your inputs.'
    if (axiosErr.response?.status === 409) return 'Email or username already exists.'
  }
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred.'
}
