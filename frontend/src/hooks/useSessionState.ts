import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'

// ─── Tipos ────────────────────────────────────────────────────────────────────

export type SessionMode = 'exploration' | 'tension' | 'combat'

export interface CombatEnemy {
  name: string
  slug: string
  hp_current: number
  hp_max: number
}

export interface SessionState {
  mode: SessionMode
  enemies: CombatEnemy[]
  currentScene: string | null
  isLoading: boolean
}

interface RawSessionState {
  session_mode: 'exploration' | 'combat'
  combat: {
    in_combat: boolean
    enemies: CombatEnemy[]
  }
  current_scene: string | null
}

// Palavras-chave no texto do GM que indicam tensão mesmo sem combate ativo
const TENSION_KEYWORDS = [
  'alerta', 'detectou', 'suspeita', 'persegu', 'furtiv',
  'espreita', 'ameaça', 'perigo', 'guardas', 'patrulha',
  'armadilha', 'emboscada', 'silêncio mortal', 'tensão',
]

export function detectTension(gmText: string): boolean {
  const lower = gmText.toLowerCase()
  return TENSION_KEYWORDS.some((kw) => lower.includes(kw))
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Observa o estado da sessão (modo, inimigos, cena atual).
 *
 * Uso:
 *   const { mode, enemies, currentScene, isLoading, refresh } = useSessionState(sessionId)
 *
 * Chame `refresh()` sempre que o WS receber 'session_state_changed' ou 'round_completed'.
 */
export function useSessionState(sessionId: string | null): SessionState & { refresh: () => void } {
  const [mode, setMode] = useState<SessionMode>('exploration')
  const [enemies, setEnemies] = useState<CombatEnemy[]>([])
  const [currentScene, setCurrentScene] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!sessionId) return
    try {
      const data = await api.get<RawSessionState>(`/sessions/${sessionId}/state`)
      if (data.combat.in_combat) {
        setMode('combat')
        setEnemies(data.combat.enemies)
      } else {
        setEnemies([])
        // Mantém tensão se já estava — o chamador pode sobrepor com detectTension()
        setMode((prev) => (prev === 'combat' ? 'exploration' : prev))
      }
      setCurrentScene(data.current_scene)
    } catch {
      // Silencia erros de rede — estado anterior mantido
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  // Carrega estado inicial ao montar ou quando sessionId muda
  useEffect(() => {
    setIsLoading(true)
    void refresh()
  }, [refresh])

  return { mode, enemies, currentScene, isLoading, refresh }
}
