/**
 * Tests for useAuth hook (thin wrapper over AuthContext).
 *
 * Full integration tests require AuthProvider + MemoryRouter and are
 * exercised via CharacterCreationModal.test.tsx and page-level tests.
 * Unit-level smoke tests live here.
 */
import { describe, it, expect } from 'vitest'
import { useAuth } from '../hooks/useAuth'

describe('useAuth module', () => {
  it('exports useAuth as a function', () => {
    expect(typeof useAuth).toBe('function')
  })
})
