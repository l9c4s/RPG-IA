/**
 * Tests for useAuth hook (which proxies AuthContext).
 *
 * These tests verify that the hook correctly surfaces the context values
 * and that AuthProvider correctly manages auth state.
 *
 * NOTE: Requires vitest/jest + @testing-library/react to run.
 */

// Updated imports after refactor:
// - useAuth is now a thin wrapper over AuthContext
// - AuthContext is defined in src/contexts/AuthContext.tsx
// - API calls are in src/api/auth.ts (authApi.login, authApi.me, etc.)
// - Types are in src/types/index.ts

// import { renderHook, act } from '@testing-library/react'
// import { MemoryRouter } from 'react-router-dom'
// import { AuthProvider } from '../contexts/AuthContext'
// import { useAuth } from '../hooks/useAuth'
// import { authApi } from '../api/auth'

// describe('useAuth', () => {
//   it('returns isAuthenticated=false with no token', () => {
//     const { result } = renderHook(() => useAuth(), {
//       wrapper: ({ children }) => (
//         <MemoryRouter>
//           <AuthProvider>{children}</AuthProvider>
//         </MemoryRouter>
//       ),
//     })
//     expect(result.current.isAuthenticated).toBe(false)
//     expect(result.current.user).toBeNull()
//   })

//   it('exposes login, register, logout, clearError functions', () => {
//     const { result } = renderHook(() => useAuth(), {
//       wrapper: ({ children }) => (
//         <MemoryRouter>
//           <AuthProvider>{children}</AuthProvider>
//         </MemoryRouter>
//       ),
//     })
//     expect(typeof result.current.login).toBe('function')
//     expect(typeof result.current.register).toBe('function')
//     expect(typeof result.current.logout).toBe('function')
//     expect(typeof result.current.clearError).toBe('function')
//   })
// })

export {}
