import { useState, useRef, useCallback, useEffect } from 'react'
import type { WSMessage, WSMessageType } from '../types'

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'reconnecting'

interface UseWebSocketOptions {
  onMessage?:             (message: WSMessage) => void
  reconnectInterval?:     number
  maxReconnectAttempts?:  number
}

interface UseWebSocketReturn {
  connect:          (sessionId: number | string, playerId: number | string) => void
  disconnect:       () => void
  send:             (message: WSMessage | Record<string, unknown>) => void
  connectionStatus: ConnectionStatus
  lastError:        string | null
}

const PING_INTERVAL_MS     = 25_000
const DEFAULT_RECONNECT_MS = 3_000
const MAX_RECONNECT        = 5

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    onMessage,
    reconnectInterval = DEFAULT_RECONNECT_MS,
    maxReconnectAttempts = MAX_RECONNECT,
  } = options

  const wsRef             = useRef<WebSocket | null>(null)
  const pingTimerRef      = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectCountRef = useRef(0)
  const sessionParamsRef  = useRef<{ sessionId: string; playerId: string } | null>(null)
  const onMessageRef      = useRef(onMessage)

  // Keep callback ref fresh without re-triggering effects
  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])

  const [status,    setStatus]    = useState<ConnectionStatus>('disconnected')
  const [lastError, setLastError] = useState<string | null>(null)

  // ── Cleanup helpers ──────────────────────────────────────────────────────
  const clearPing = () => {
    if (pingTimerRef.current) clearInterval(pingTimerRef.current)
    pingTimerRef.current = null
  }

  const clearReconnect = () => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
    reconnectTimerRef.current = null
  }

  const closeSocket = (reason?: string) => {
    clearPing()
    if (wsRef.current) {
      wsRef.current.onclose = null  // prevent reconnect loop on manual close
      wsRef.current.close(1000, reason ?? 'Client closed')
      wsRef.current = null
    }
  }

  // ── Core connect ─────────────────────────────────────────────────────────
  const connectInternal = useCallback(
    (sessionId: string, playerId: string) => {
      closeSocket()
      clearReconnect()

      setStatus('connecting')
      setLastError(null)

      const rawToken = localStorage.getItem('access_token')
      const token    = rawToken ? (JSON.parse(rawToken) as string) : ''
      const proto   = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const host    = window.location.host
      const url     = `${proto}://${host}/ws/session/${sessionId}/player/${playerId}?token=${encodeURIComponent(token)}`

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('connected')
        setLastError(null)
        reconnectCountRef.current = 0

        // Keep-alive pings
        pingTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping', payload: null } satisfies WSMessage))
          }
        }, PING_INTERVAL_MS)
      }

      ws.onmessage = (event: MessageEvent<string>) => {
        try {
          const msg = JSON.parse(event.data) as WSMessage
          if (msg.type === ('pong' satisfies WSMessageType)) return
          onMessageRef.current?.(msg)
        } catch {
          // Non-JSON frames — ignore
        }
      }

      ws.onerror = () => {
        setLastError('WebSocket connection error.')
        setStatus('error')
      }

      ws.onclose = (event) => {
        clearPing()
        if (event.wasClean) {
          setStatus('disconnected')
          return
        }

        // Attempt reconnect
        if (reconnectCountRef.current < maxReconnectAttempts) {
          reconnectCountRef.current += 1
          setStatus('reconnecting')
          reconnectTimerRef.current = setTimeout(() => {
            if (sessionParamsRef.current) {
              connectInternal(
                sessionParamsRef.current.sessionId,
                sessionParamsRef.current.playerId,
              )
            }
          }, reconnectInterval)
        } else {
          setStatus('error')
          setLastError('Could not reconnect to the game server. Refresh the page to try again.')
        }
      }
    },
    [maxReconnectAttempts, reconnectInterval],
  )

  // ── Public API ────────────────────────────────────────────────────────────
  const connect = useCallback(
    (sessionId: number | string, playerId: number | string): void => {
      const sid = String(sessionId)
      const pid = String(playerId)
      sessionParamsRef.current     = { sessionId: sid, playerId: pid }
      reconnectCountRef.current    = 0
      connectInternal(sid, pid)
    },
    [connectInternal],
  )

  const disconnect = useCallback((): void => {
    sessionParamsRef.current  = null
    reconnectCountRef.current = maxReconnectAttempts // prevent auto-reconnect
    clearReconnect()
    closeSocket('User disconnected')
    setStatus('disconnected')
  }, [maxReconnectAttempts])

  const send = useCallback((message: WSMessage | Record<string, unknown>): void => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('[WS] Attempted to send while not connected:', message)
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      sessionParamsRef.current  = null
      reconnectCountRef.current = maxReconnectAttempts
      clearPing()
      clearReconnect()
      closeSocket('Component unmounted')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { connect, disconnect, send, connectionStatus: status, lastError }
}
