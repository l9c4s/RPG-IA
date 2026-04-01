/**
 * Tests for useWebSocket hook.
 *
 * NOTE: Requires vitest/jest + @testing-library/react to run.
 */

// Updated imports after refactor:
// - WSMessage type is now in src/types/index.ts (not src/api/types.ts)
// - Hook is at src/hooks/useWebSocket.ts (unchanged)

// import { renderHook, act } from '@testing-library/react'
// import { useWebSocket } from '../hooks/useWebSocket'

// describe('useWebSocket', () => {
//   it('starts with disconnected status', () => {
//     const { result } = renderHook(() => useWebSocket())
//     expect(result.current.connectionStatus).toBe('disconnected')
//     expect(result.current.lastError).toBeNull()
//   })

//   it('exposes connect, disconnect, send functions', () => {
//     const { result } = renderHook(() => useWebSocket())
//     expect(typeof result.current.connect).toBe('function')
//     expect(typeof result.current.disconnect).toBe('function')
//     expect(typeof result.current.send).toBe('function')
//   })

//   it('calls onMessage callback when message arrives', () => {
//     // Mock WebSocket and verify onMessage is triggered
//   })
// })

export {}
