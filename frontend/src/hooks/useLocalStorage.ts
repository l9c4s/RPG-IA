import { useState, useEffect, useCallback } from 'react'

/**
 * Generic typed hook for localStorage with cross-tab sync.
 * Returns [value, setValue, removeValue].
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): [T, (value: T) => void, () => void] {
  const readValue = useCallback((): T => {
    try {
      const item = window.localStorage.getItem(key)
      return item ? (JSON.parse(item) as T) : initialValue
    } catch {
      return initialValue
    }
  }, [key, initialValue])

  const [storedValue, setStoredValue] = useState<T>(readValue)

  const setValue = useCallback(
    (value: T): void => {
      try {
        window.localStorage.setItem(key, JSON.stringify(value))
        setStoredValue(value)
        // Notify other tabs
        window.dispatchEvent(new StorageEvent('storage', { key, newValue: JSON.stringify(value) }))
      } catch {
        console.warn(`[useLocalStorage] Failed to set key "${key}"`)
      }
    },
    [key],
  )

  const removeValue = useCallback((): void => {
    try {
      window.localStorage.removeItem(key)
      setStoredValue(initialValue)
      window.dispatchEvent(new StorageEvent('storage', { key, newValue: null }))
    } catch {
      console.warn(`[useLocalStorage] Failed to remove key "${key}"`)
    }
  }, [key, initialValue])

  // Sync across tabs
  useEffect(() => {
    function handleStorage(e: StorageEvent): void {
      if (e.key !== key) return
      try {
        setStoredValue(e.newValue ? (JSON.parse(e.newValue) as T) : initialValue)
      } catch {
        setStoredValue(initialValue)
      }
    }

    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [key, initialValue])

  return [storedValue, setValue, removeValue]
}
