/**
 * Tests for useWebSocket hook.
 *
 * Full behavioural tests require a WebSocket mock server.
 * Unit-level smoke tests live here.
 */
import { describe, it, expect } from 'vitest'
import { useWebSocket } from '../hooks/useWebSocket'

describe('useWebSocket module', () => {
  it('exports useWebSocket as a function', () => {
    expect(typeof useWebSocket).toBe('function')
  })
})
