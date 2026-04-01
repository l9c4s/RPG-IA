import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'
import { useLocalStorage } from '../hooks/useLocalStorage'
import type { User, Token } from '../types'

// ─── Context value shape ───────────────────────────────────────────────────
interface AuthContextValue {
  user:            User | null
  isLoading:       boolean
  error:           string | null
  isAuthenticated: boolean
  login:           (email: string, password: string) => Promise<void>
  register:        (username: string, email: string, password: string) => Promise<void>
  logout:          () => void
  clearError:      () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

// ─── Provider ─────────────────────────────────────────────────────────────
export function AuthProvider({ children }: { children: ReactNode }): React.ReactElement {
  const navigate = useNavigate()

  const [token,     setToken,    removeToken] = useLocalStorage<string | null>('access_token', null)
  const [storedUser, setStoredUser, removeStoredUser] = useLocalStorage<User | null>('user', null)

  const [user,      setUser]      = useState<User | null>(storedUser)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error,     setError]     = useState<string | null>(null)

  // On mount: verify token is still valid
  useEffect(() => {
    if (!token) return

    setIsLoading(true)
    authApi
      .me()
      .then((res) => {
        const verifiedUser = res.data
        setStoredUser(verifiedUser)
        setUser(verifiedUser)
        setIsLoading(false)
      })
      .catch(() => {
        removeToken()
        removeStoredUser()
        setUser(null)
        setIsLoading(false)
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Login ────────────────────────────────────────────────────────────────
  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      setIsLoading(true)
      setError(null)
      try {
        const res  = await authApi.login({ email, password })
        const data: Token = res.data
        setToken(data.access_token)
        setStoredUser(data.user)
        setUser(data.user)
        setIsLoading(false)
        navigate('/dashboard')
      } catch (err: unknown) {
        const message = extractErrorMessage(err)
        setError(message)
        setIsLoading(false)
        throw new Error(message)
      }
    },
    [navigate, setToken, setStoredUser],
  )

  // ── Register ─────────────────────────────────────────────────────────────
  const register = useCallback(
    async (username: string, email: string, password: string): Promise<void> => {
      setIsLoading(true)
      setError(null)
      try {
        const res  = await authApi.register({ username, email, password })
        // Register returns User; we need a token. Try login after register.
        // If the API returns a Token instead, handle that here.
        const payload = res.data as unknown as Token
        if (payload.access_token) {
          setToken(payload.access_token)
          setStoredUser(payload.user)
          setUser(payload.user)
        } else {
          // API returned just a User — do a follow-up login
          const loginRes = await authApi.login({ email, password })
          const loginData: Token = loginRes.data
          setToken(loginData.access_token)
          setStoredUser(loginData.user)
          setUser(loginData.user)
        }
        setIsLoading(false)
        navigate('/dashboard')
      } catch (err: unknown) {
        const message = extractErrorMessage(err)
        setError(message)
        setIsLoading(false)
        throw new Error(message)
      }
    },
    [navigate, setToken, setStoredUser],
  )

  // ── Logout ────────────────────────────────────────────────────────────────
  const logout = useCallback((): void => {
    removeToken()
    removeStoredUser()
    setUser(null)
    setError(null)
    navigate('/login')
  }, [navigate, removeToken, removeStoredUser])

  const clearError = useCallback((): void => {
    setError(null)
  }, [])

  const value: AuthContextValue = {
    user,
    isLoading,
    error,
    isAuthenticated: user !== null,
    login,
    register,
    logout,
    clearError,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// ─── Hook ─────────────────────────────────────────────────────────────────
export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuthContext must be used within AuthProvider')
  }
  return ctx
}

// ─── Utility ───────────────────────────────────────────────────────────────
function extractErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as { response?: { data?: { detail?: string }; status?: number } }
    if (axiosErr.response?.data?.detail) return axiosErr.response.data.detail
    if (axiosErr.response?.status === 401) return 'Credenciais inválidas.'
    if (axiosErr.response?.status === 422) return 'Erro de validação. Verifique os campos.'
    if (axiosErr.response?.status === 409) return 'Email ou nome de usuário já existe.'
  }
  if (err instanceof Error) return err.message
  return 'Ocorreu um erro inesperado.'
}
