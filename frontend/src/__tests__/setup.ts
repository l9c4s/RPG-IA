// Test environment setup
// This file is loaded before each test file.
// Add global test utilities, mocks, and polyfills here.
import '@testing-library/jest-dom'

// Example: mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem:    (key: string) => store[key] ?? null,
    setItem:    (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear:      () => { store = {} },
  }
})()

Object.defineProperty(window, 'localStorage', { value: localStorageMock })
