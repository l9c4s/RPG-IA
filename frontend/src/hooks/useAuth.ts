import { useAuthContext } from '../contexts/AuthContext'

/**
 * Convenience hook — re-exports from AuthContext for backwards compatibility.
 */
export function useAuth() {
  return useAuthContext()
}
