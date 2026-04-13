import React, {
  useState, useEffect, useRef, useCallback, KeyboardEvent
} from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  Send, Wifi, WifiOff, AlertTriangle, Users,
  Map, BookOpen, ChevronLeft, Dice1, Dice6, Volume2,
  Image as ImageIcon, Heart, Shield, Zap, X, Compass, Swords, Skull
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { useWebSocket } from '../hooks/useWebSocket'
import { useSessionState, detectTension, type SessionMode, type CombatEnemy } from '../hooks/useSessionState'
import { Spinner } from './ui/Spinner'
import { Badge } from './ui/Badge'
import type {
  ChatMessage, Character, CharacterStatus, WSMessage,
  DiceRoll, StateUpdate, Campaign
} from '../types'
import WorldMap from './WorldMap'
import RoundPanel, { type RoundState, type RoundPhase, type InitiativeEntry, type GMRoundResponse } from './RoundPanel'

// ─── Connection indicator ──────────────────────────────────────────────────
type ConnStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'reconnecting'

function ConnectionBadge({ status }: { status: ConnStatus }): React.ReactElement {
  const configs: Record<ConnStatus, { label: string; color: string; pulse: boolean }> = {
    connected:     { label: 'Connected',     color: 'text-green-400',  pulse: false },
    connecting:    { label: 'Connecting…',   color: 'text-amber-400',  pulse: true  },
    reconnecting:  { label: 'Reconnecting…', color: 'text-amber-400',  pulse: true  },
    disconnected:  { label: 'Disconnected',  color: 'text-slate-500',  pulse: false },
    error:         { label: 'Error',         color: 'text-red-400',    pulse: false },
  }
  const cfg = configs[status]

  return (
    <div className={`flex items-center gap-1.5 text-xs ${cfg.color}`}>
      {status === 'connected' ? (
        <Wifi className="w-3.5 h-3.5" />
      ) : status === 'error' || status === 'disconnected' ? (
        <WifiOff className="w-3.5 h-3.5" />
      ) : (
        <Spinner size="sm" />
      )}
      <span className={cfg.pulse ? 'animate-pulse' : ''}>{cfg.label}</span>
    </div>
  )
}

// ─── D20 tier classification ───────────────────────────────────────────────
function d20Tier(roll: number): { label: string; className: string } | null {
  if (roll >= 16) return { label: 'Sucesso Crítico ✦', className: 'bg-emerald-900/60 border-emerald-500/60 text-emerald-300' }
  if (roll >= 10) return { label: 'Sucesso',           className: 'bg-slate-700/60 border-slate-500/60 text-slate-300'     }
  if (roll >= 5)  return { label: 'Falha',             className: 'bg-amber-900/60 border-amber-600/60 text-amber-300'     }
  return               { label: 'Falha Crítica ✗',  className: 'bg-red-900/60 border-red-600/60 text-red-300'           }
}

// ─── Dice result display ───────────────────────────────────────────────────
function DiceRollDisplay({ roll }: { roll: DiceRoll }): React.ReactElement {
  const isCrit   = roll.expr.includes('d20') && roll.result === 20
  const isFumble = roll.expr.includes('d20') && roll.result === 1

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold font-serif border ${
      isCrit
        ? 'bg-amber-900/60 border-amber-500/60 text-amber-300 shadow-amber'
        : isFumble
        ? 'bg-red-900/60 border-red-500/60 text-red-300'
        : 'bg-slate-700/60 border-slate-600/60 text-slate-300'
    }`}>
      {isCrit ? <Dice6 className="w-3 h-3 text-amber-400" /> : <Dice1 className="w-3 h-3 text-slate-400" />}
      {roll.expr} = <strong>{roll.result}</strong>
      {roll.breakdown && <span className="text-slate-400 font-normal">({roll.breakdown})</span>}
    </span>
  )
}

// ─── State update display ──────────────────────────────────────────────────
function StateUpdateDisplay({ update }: { update: StateUpdate }): React.ReactElement {
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-purple-900/40 border border-purple-700/40 rounded px-2 py-0.5 text-purple-300">
      <Zap className="w-3 h-3" />
      {update.field}: {update.value}
    </span>
  )
}

// ─── Avatar ────────────────────────────────────────────────────────────────
function Avatar({ label, color }: { label: string; color: string }) {
  return (
    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${color}`}>
      {label}
    </div>
  )
}

// ─── Single chat message ───────────────────────────────────────────────────
interface MessageBubbleProps { message: ChatMessage }

function MessageBubble({ message }: MessageBubbleProps): React.ReactElement {
  const [audioPlaying, setAudioPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    if (message.audio_url) {
      audioRef.current = new Audio(message.audio_url)
      audioRef.current.play().catch(() => {})
      setAudioPlaying(true)
      audioRef.current.onended = () => setAudioPlaying(false)
    }
    return () => { audioRef.current?.pause() }
  }, [message.audio_url])

  const timeStr = new Date(message.timestamp).toLocaleTimeString('pt-BR', {
    hour: '2-digit', minute: '2-digit',
  })

  // ── System message — centralizado ──────────────────────────────────────
  if (message.role === 'system') {
    return (
      <div className="flex justify-center my-1 animate-fade-in">
        <span className="text-xs text-slate-500 italic bg-slate-800/60 border border-slate-700/40 rounded-full px-3 py-1">
          {message.content}
        </span>
      </div>
    )
  }

  // ── Opening narration — card imersivo full-width ────────────────────────
  if (message.role === 'gm_opening') {
    return (
      <div className="my-4 animate-fade-in px-2">
        <div className="relative border border-amber-700/50 bg-gradient-to-b from-amber-950/30 to-slate-900/60 rounded-xl p-5 shadow-lg">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-4 h-4 text-amber-400" />
            <span className="text-amber-400 font-serif text-xs font-semibold tracking-widest uppercase">
              Abertura da Campanha
            </span>
            <span className="text-slate-600 text-xs ml-auto">{timeStr}</span>
          </div>
          <p className="text-slate-200 font-serif leading-relaxed whitespace-pre-wrap italic">
            {message.content}
          </p>
        </div>
      </div>
    )
  }

  const isGM        = message.role === 'gm'
  const isPlayer    = message.role === 'player'
  const isCompanion = message.role === 'ai_companion'
  const isRight     = isPlayer || isCompanion  // player + IA companion → direita

  // Iniciais para o avatar
  const name    = message.character_name ?? (isGM ? 'DM' : '?')
  const initials = name.split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()

  const avatarColor = isGM
    ? 'bg-amber-800/70 text-amber-200 border border-amber-600/50'
    : isCompanion
    ? 'bg-purple-800/70 text-purple-200 border border-purple-600/50'
    : 'bg-blue-800/70 text-blue-200 border border-blue-600/50'

  const bubbleBg = isGM
    ? 'bg-slate-800/80 border border-amber-800/30 text-slate-100'
    : isCompanion
    ? 'bg-purple-950/60 border border-purple-700/40 text-slate-200'
    : 'bg-blue-950/70 border border-blue-700/40 text-slate-100'

  const senderColor = isGM ? 'text-amber-400' : isCompanion ? 'text-purple-400' : 'text-blue-400'

  return (
    <div className={`flex items-end gap-2 animate-fade-in px-2 ${isRight ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <Avatar label={initials} color={avatarColor} />

      {/* Coluna com rótulo + bolha */}
      <div className={`flex flex-col gap-1 max-w-[75%] ${isRight ? 'items-end' : 'items-start'}`}>

        {/* Rótulo: nome + badge IA + hora */}
        <div className={`flex items-center gap-1.5 text-[11px] ${senderColor} ${isRight ? 'flex-row-reverse' : 'flex-row'}`}>
          <span className="font-serif font-semibold">
            {isGM ? 'Dungeon Master' : name}
          </span>
          {isCompanion && (
            <span className="px-1.5 py-px rounded text-[9px] font-bold bg-purple-900/60 border border-purple-700/50 text-purple-300">
              IA
            </span>
          )}
          <span className="text-slate-600">{timeStr}</span>
        </div>

        {/* Bolha */}
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${bubbleBg} ${
          isRight ? 'rounded-br-sm' : 'rounded-bl-sm'
        }`}>

          {/* Texto */}
          <p className="whitespace-pre-wrap">{message.content}</p>

          {/* Tier badge — apenas para ações de jogador/companion com d20 */}
          {(isPlayer || isCompanion) && message.dice_rolls && message.dice_rolls.length > 0 && (() => {
            const d20Roll = message.dice_rolls.find(r => r.expr === 'd20')
            if (!d20Roll) return null
            const tier = d20Tier(d20Roll.result)
            if (!tier) return null
            return (
              <div className="mt-2">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border ${tier.className}`}>
                  {tier.label}
                </span>
              </div>
            )
          })()}

          {/* Dados rolados */}
          {message.dice_rolls && message.dice_rolls.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-white/10">
              {message.dice_rolls.map((roll, i) => (
                <DiceRollDisplay key={i} roll={roll} />
              ))}
            </div>
          )}

          {/* Mudanças de estado */}
          {message.state_updates && message.state_updates.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {message.state_updates.map((upd, i) => (
                <StateUpdateDisplay key={i} update={upd} />
              ))}
            </div>
          )}

          {/* Imagem de cena */}
          {message.image_url && (
            <div className="mt-3 rounded-xl overflow-hidden border border-amber-700/30">
              <img
                src={message.image_url}
                alt="Cena ilustrada"
                className="w-full object-cover max-h-56"
                loading="lazy"
              />
              <p className="text-[10px] text-center text-amber-700/60 py-1 flex items-center justify-center gap-1">
                <ImageIcon className="w-3 h-3" /> Cena gerada por IA
              </p>
            </div>
          )}

          {/* Áudio */}
          {message.audio_url && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-amber-400">
              <Volume2 className={`w-3.5 h-3.5 ${audioPlaying ? 'animate-pulse' : ''}`} />
              {audioPlaying ? 'Reproduzindo narração…' : 'Narração reproduzida'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Mini character status ─────────────────────────────────────────────────
interface CharStatusPanelProps {
  character: Character
  onExpand:  () => void
}

function CharStatusPanel({ character, onExpand }: CharStatusPanelProps): React.ReactElement {
  const status  = character.status
  const attrs   = character.attributes
  const hpMax   = status?.hp_max ?? 1
  const hpCur   = status?.hp_current ?? 0
  const hpPercent = Math.max(0, Math.min(100, (hpCur / hpMax) * 100))
  const hpColor   = hpPercent > 50 ? 'bg-green-600' : hpPercent > 25 ? 'bg-amber-500' : 'bg-red-600'

  return (
    <div className="card-rune p-4 space-y-3">
      {/* Name & class */}
      <div className="flex items-center justify-between">
        <div>
          <p className="font-serif text-amber-400 font-semibold text-sm">{character.name}</p>
          <p className="text-slate-500 text-xs">
            Lvl {character.level} {character.character_class}
          </p>
        </div>
        <button
          onClick={onExpand}
          className="text-xs text-slate-500 hover:text-amber-400 transition-colors underline"
        >
          Full sheet
        </button>
      </div>

      {/* HP bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-1 text-slate-400">
            <Heart className="w-3 h-3 text-red-500" /> HP
          </span>
          <span className="text-slate-300">
            {hpCur}{(status?.hp_temp ?? 0) > 0 && <span className="text-blue-400">+{status?.hp_temp}</span>} / {hpMax}
          </span>
        </div>
        <div className="hp-track">
          <div
            className={`h-full ${hpColor} transition-all duration-500 rounded-full`}
            style={{ width: `${hpPercent}%` }}
          />
        </div>
      </div>

      {/* AC + Speed */}
      <div className="flex items-center gap-3 text-xs">
        <span className="flex items-center gap-1 text-slate-400">
          <Shield className="w-3 h-3 text-blue-400" /> AC {attrs?.armor_class ?? 10}
        </span>
        <span className="flex items-center gap-1 text-slate-400">
          <Zap className="w-3 h-3 text-amber-400" /> {attrs?.speed ?? 30} ft
        </span>
      </div>

      {/* Conditions */}
      {(status?.conditions ?? []).length > 0 && (
        <div className="flex flex-wrap gap-1">
          {(status?.conditions ?? []).map((c) => (
            <span key={c} className="badge-condition">{c}</span>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Kill Modal ───────────────────────────────────────────────────────────────

interface KillEvent {
  enemy_name: string
  enemy_type: string
  killer: string
  xp_gained: number
  loot: Array<{ item: string; qty: number }>
  hp_max: number
  cr: number
}

function KillModal({ event, onClose }: { event: KillEvent; onClose: () => void }): React.ReactElement {
  // Auto-dismiss após 6 segundos
  useEffect(() => {
    const t = setTimeout(onClose, 6000)
    return () => clearTimeout(t)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
      <div
        className="pointer-events-auto relative w-full max-w-sm mx-4 rounded-xl border border-red-700/60
                   bg-gradient-to-b from-slate-900 via-red-950/40 to-slate-900
                   shadow-2xl shadow-red-900/40 animate-[fadeInScale_0.3s_ease-out]"
        style={{ animation: 'fadeInScale 0.3s ease-out' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <div className="flex items-center gap-2">
            <Skull className="w-5 h-5 text-red-400" />
            <span className="text-sm font-bold text-red-300 tracking-wide uppercase">
              Inimigo Derrotado
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Enemy name */}
        <div className="px-4 py-2 border-t border-b border-red-900/40">
          <p className="text-lg font-bold text-white text-center">{event.enemy_name}</p>
          <p className="text-xs text-slate-400 text-center mt-0.5">
            eliminado por <span className="text-amber-300 font-semibold">{event.killer}</span>
          </p>
        </div>

        {/* XP */}
        <div className="px-4 py-3 flex items-center justify-center gap-2">
          <Zap className="w-5 h-5 text-amber-400" />
          <span className="text-2xl font-bold text-amber-300 tabular-nums">
            +{event.xp_gained}
          </span>
          <span className="text-sm text-amber-500 font-semibold">XP</span>
        </div>

        {/* Loot */}
        {event.loot.length > 0 && (
          <div className="px-4 pb-3 space-y-1">
            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">
              Itens obtidos
            </p>
            {event.loot.map((l, i) => (
              <div key={i} className="flex items-center gap-2 text-sm text-slate-300">
                <span className="text-slate-500">•</span>
                <span>{l.item}</span>
                {l.qty > 1 && <span className="text-slate-500 text-xs">×{l.qty}</span>}
              </div>
            ))}
          </div>
        )}

        {/* Progress bar: auto-dismiss */}
        <div className="h-0.5 rounded-b-xl bg-red-900/40 overflow-hidden">
          <div
            className="h-full bg-red-600/60 rounded-b-xl"
            style={{ animation: 'shrink 6s linear forwards' }}
          />
        </div>
      </div>

      <style>{`
        @keyframes fadeInScale {
          from { opacity: 0; transform: scale(0.85) translateY(-12px); }
          to   { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes shrink {
          from { width: 100%; }
          to   { width: 0%; }
        }
      `}</style>
    </div>
  )
}

// ─── Atmosphere Panel ─────────────────────────────────────────────────────────

const MOOD_CONFIG: Record<SessionMode, {
  label: string
  icon: React.ReactNode
  color: string
  pulse: boolean
  bg: string
}> = {
  exploration: {
    label: 'Explorando',
    icon: <Compass className="w-4 h-4" />,
    color: 'text-slate-300',
    bg: 'bg-slate-800/60 border-slate-700/50',
    pulse: false,
  },
  tension: {
    label: 'Tensão',
    icon: <AlertTriangle className="w-4 h-4" />,
    color: 'text-amber-400',
    bg: 'bg-amber-950/40 border-amber-700/40',
    pulse: true,
  },
  combat: {
    label: 'Em Combate',
    icon: <Swords className="w-4 h-4" />,
    color: 'text-red-400',
    bg: 'bg-red-950/40 border-red-700/40',
    pulse: true,
  },
}

function EnemyHpBar({ enemy }: { enemy: CombatEnemy }): React.ReactElement {
  const pct = Math.max(0, Math.min(100, (enemy.hp_current / enemy.hp_max) * 100))
  const barColor = pct > 50 ? 'bg-green-600' : pct > 25 ? 'bg-amber-500' : 'bg-red-600'
  const isDead = enemy.hp_current <= 0

  return (
    <div className={`space-y-1 ${isDead ? 'opacity-40' : ''}`}>
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1 text-slate-300 font-medium truncate max-w-[70%]">
          {isDead && <Skull className="w-3 h-3 text-slate-500 shrink-0" />}
          {enemy.name}
        </span>
        <span className="text-slate-400 tabular-nums shrink-0">
          {enemy.hp_current} / {enemy.hp_max}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-700 overflow-hidden">
        <div
          className={`h-full ${barColor} transition-all duration-500 rounded-full`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function AtmospherePanel({
  mode,
  enemies,
  isLoading,
}: {
  mode: SessionMode
  enemies: CombatEnemy[]
  isLoading: boolean
}): React.ReactElement {
  const cfg = MOOD_CONFIG[mode]

  return (
    <div className="sidebar-section space-y-3">
      {/* Indicador de modo */}
      <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${cfg.bg}`}>
        <span className={cfg.color}>{cfg.icon}</span>
        <span className={`text-xs font-semibold tracking-wide ${cfg.color} ${cfg.pulse ? 'animate-pulse' : ''}`}>
          {isLoading ? '…' : cfg.label}
        </span>
      </div>

      {/* Lista de inimigos — só aparece em combate */}
      {mode === 'combat' && enemies.length > 0 && (
        <div className="space-y-2.5">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">Inimigos</p>
          {enemies.map((enemy) => (
            <EnemyHpBar key={enemy.slug} enemy={enemy} />
          ))}
        </div>
      )}

      {/* Placeholder quando não há combate */}
      {mode !== 'combat' && (
        <p className="text-[11px] text-slate-600 leading-relaxed">
          {mode === 'tension'
            ? 'Algo está errado. Fique alerta.'
            : 'Nenhum encontro ativo.'}
        </p>
      )}
    </div>
  )
}

// ─── Main GameSession component ────────────────────────────────────────────
export default function GameSession(): React.ReactElement {
  const { id: campaignId } = useParams<{ id: string }>()
  const { user }           = useAuth()
  const navigate           = useNavigate()

  const [campaign,        setCampaign]        = useState<Campaign | null>(null)
  const [character,       setCharacter]       = useState<Character | null>(null)
  const [myCharacter,     setMyCharacter]     = useState<Character | null>(null) // personagem do jogador logado — nunca muda ao clicar na sidebar
  const [characterImgUrl, setCharacterImgUrl] = useState<string | null>(null)
  const [party,           setParty]           = useState<Character[]>([])
  const [sessionId,       setSessionId]       = useState<string | null>(null)
  const [messages,        setMessages]        = useState<ChatMessage[]>([])
  const [inputText,       setInputText]       = useState('')
  const [activeTab,       setActiveTab]       = useState<'chat' | 'sheet' | 'map'>('chat')
  const [voiceActive,     setVoiceActive]     = useState(false)
  const [isSending,       setIsSending]       = useState(false)
  const [isLoading,       setIsLoading]       = useState(true)
  const [gateBlocked,     setGateBlocked]     = useState(false)
  const [showMap,         setShowMap]         = useState(false)
  const [gmTyping,        setGmTyping]        = useState(false)

  // ── Kill modal queue ──────────────────────────────────────────────────────
  const [killQueue,    setKillQueue]    = useState<KillEvent[]>([])
  const currentKill = killQueue[0] ?? null
  const dismissKill = useCallback(() => {
    setKillQueue((q) => q.slice(1))
  }, [])

  // ── Round state ───────────────────────────────────────────────────────────
  const DEFAULT_ROUND: RoundState = {
    roundId: '', roundNumber: 0, phase: 'idle',
    submittedCount: 0, expectedCount: 0,
    submittedCharacterIds: [], initiative: [], gmResponses: [],
  }
  const [round,             setRound]             = useState<RoundState>(DEFAULT_ROUND)
  const [isStartingRound,   setIsStartingRound]   = useState(false)
  const [useRoundMode,      setUseRoundMode]       = useState(true)
  /** Todos os personagens controlados pelo usuário logado (≥1 em co-op) */
  const [myCharacters,      setMyCharacters]       = useState<Array<{ id: string; name: string }>>([])
  /** Índice do personagem ativo no switcher co-op */
  const [activeMyCharIdx,   setActiveMyCharIdx]    = useState(0)

  const messagesEndRef    = useRef<HTMLDivElement>(null)
  const textareaRef       = useRef<HTMLTextAreaElement>(null)

  // ── Session state observer ────────────────────────────────────────────────
  // Atualizado a cada 'session_state_changed' recebido via WS
  const {
    mode: sessionMode,
    enemies: combatEnemies,
    isLoading: sessionStateLoading,
    refresh: refreshSessionState,
  } = useSessionState(sessionId)

  // Tensão detectada cliente-side pelo texto do GM (sem combate ativo)
  const [hasTension, setHasTension] = useState(false)

  // Modo exibido = prioridade: combat > tension > exploration
  const displayMode: SessionMode =
    sessionMode === 'combat' ? 'combat' : hasTension ? 'tension' : 'exploration'

  // ── WebSocket ────────────────────────────────────────────────────────────
  const handleWsMessage = useCallback((wsMsg: WSMessage) => {
    switch (wsMsg.type) {
      case 'gm_response': {
        const gm = wsMsg.payload as {
          content: string; timestamp?: string
          dice_rolls?: DiceRoll[]; state_updates?: StateUpdate[]
          image_url?: string; audio_url?: string
        }
        setGmTyping(false)
        setMessages((prev) => [
          ...prev,
          {
            id:            crypto.randomUUID(),
            role:          'gm',
            content:       gm.content,
            timestamp:     gm.timestamp ?? new Date().toISOString(),
            dice_rolls:    gm.dice_rolls,
            state_updates: gm.state_updates,
            image_url:     gm.image_url,
            audio_url:     gm.audio_url,
          } as ChatMessage,
        ])
        setHasTension(detectTension(gm.content))
        break
      }
      case 'state_update': {
        const upd = wsMsg.payload as { character_status?: CharacterStatus }
        if (upd.character_status) {
          setCharacter((prev) =>
            prev ? { ...prev, status: upd.character_status! } : prev,
          )
        }
        break
      }
      case 'system_message': {
        const sys = wsMsg.payload as { message: string; timestamp: string }
        setMessages((prev) => [
          ...prev,
          {
            id:        crypto.randomUUID(),
            role:      'system',
            content:   sys.message,
            timestamp: sys.timestamp ?? new Date().toISOString(),
          } as ChatMessage,
        ])
        break
      }
      case 'gate_blocked': {
        setGateBlocked(true)
        setGmTyping(false)
        break
      }
      case 'companion_reaction': {
        const comp = wsMsg.payload as { companion_name: string; text: string; character_id: string }
        setMessages((prev) => [
          ...prev,
          {
            id:             crypto.randomUUID(),
            role:           'ai_companion',
            content:        comp.text,
            timestamp:      new Date().toISOString(),
            character_name: comp.companion_name,
          } as ChatMessage,
        ])
        break
      }
      // ── Round events ────────────────────────────────────────────────────
      case 'round_started': {
        const p = wsMsg.payload as { round_id: string; round_number: number; expected_players: number }
        setRound({
          roundId: p.round_id,
          roundNumber: p.round_number,
          phase: 'collecting',
          submittedCount: 0,
          expectedCount: p.expected_players,
          submittedCharacterIds: [],
          initiative: [],
          gmResponses: [],
        })
        // Reseta para o primeiro personagem do usuário a cada novo round
        setActiveMyCharIdx(0)
        break
      }
      case 'action_submitted': {
        const p = wsMsg.payload as { character_name: string; character_id?: string | null; is_pass: boolean; is_ai: boolean; action_text?: string | null }
        setRound((prev) => ({
          ...prev,
          submittedCount: prev.submittedCount + 1,
          submittedCharacterIds: p.character_id
            ? [...new Set([...prev.submittedCharacterIds, p.character_id])]
            : prev.submittedCharacterIds,
        }))
        // Co-op: avança o switcher para o próximo personagem não submetido
        if (p.character_id) {
          setMyCharacters((chars) => {
            setActiveMyCharIdx((idx) => {
              const nextIdx = chars.findIndex(
                (c, i) => i !== idx && c.id !== p.character_id
              )
              return nextIdx >= 0 ? nextIdx : idx
            })
            return chars
          })
        }
        if (p.is_ai && p.action_text) {
          // Companion IA: mostra a ação declarada no chat como mensagem do companion
          setMessages((prev) => [
            ...prev,
            {
              id:             crypto.randomUUID(),
              role:           'ai_companion',
              content:        p.action_text!,
              timestamp:      new Date().toISOString(),
              character_name: p.character_name,
            } as ChatMessage,
          ])
        } else {
          // Humano ou passe: mensagem de sistema discreta
          setMessages((prev) => [
            ...prev,
            {
              id:        crypto.randomUUID(),
              role:      'system',
              content:   `${p.is_ai ? '🤖 ' : ''}${p.character_name} ${p.is_pass ? 'passou a vez' : 'declarou sua ação'}.`,
              timestamp: new Date().toISOString(),
            } as ChatMessage,
          ])
        }
        break
      }
      case 'initiative_board': {
        const p = wsMsg.payload as { round_number: number; initiative: InitiativeEntry[] }
        setRound((prev) => ({
          ...prev,
          phase: 'gm_processing',
          initiative: p.initiative,
        }))
        setGmTyping(true)
        break
      }
      case 'gm_round_response': {
        const p = wsMsg.payload as GMRoundResponse
        setRound((prev) => ({
          ...prev,
          gmResponses: [...prev.gmResponses, p],
        }))

        const now = new Date().toISOString()

        setMessages((prev) => {
          const next = [...prev]

          // 1. Ação do jogador + dado de iniciativa (se não for AI companion — esses já aparecem via action_submitted)
          if (p.action_text && !p.character_name?.endsWith('(IA)')) {
            next.push({
              id:             crypto.randomUUID(),
              role:           'player' as const,
              content:        p.action_text,
              timestamp:      now,
              character_name: p.character_name,
              dice_rolls: p.d20_roll ? [{
                expr:      'd20',
                result:    p.d20_roll,
                breakdown: `Iniciativa: ${p.d20_roll}`,
              }] : undefined,
            } as ChatMessage)
          }

          // 2. Resposta do GM com dado de resultado (se houver)
          next.push({
            id:        crypto.randomUUID(),
            role:      'gm' as const,
            content:   p.gm_text,
            timestamp: now,
            dice_rolls: p.outcome_roll != null ? [{
              expr:      p.roll_results?.[0]?.expr ?? 'd20',
              result:    p.outcome_roll,
              breakdown: p.roll_results?.[0]?.expr
                ? `${p.roll_results[0].expr} = ${p.outcome_roll}`
                : String(p.outcome_roll),
            }] : undefined,
          } as ChatMessage)

          return next
        })
        // Detecta tensão pelo texto do GM do round
        if (p.gm_text) setHasTension(detectTension(p.gm_text))
        break
      }
      case 'round_completed': {
        setGmTyping(false)
        setRound((prev) => ({ ...prev, phase: 'completed' }))
        refreshSessionState()
        break
      }
      case 'session_state_changed': {
        refreshSessionState()
        break
      }
      case 'enemy_killed': {
        const kill = wsMsg.payload as KillEvent
        setKillQueue((q) => [...q, kill])
        refreshSessionState()
        break
      }
      default:
        break
    }
  }, [refreshSessionState])

  const { connect, disconnect, send, connectionStatus } = useWebSocket({
    onMessage: handleWsMessage,
  })

  // ── Initial load ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!campaignId || !user) return

    const loadSession = async () => {
      setIsLoading(true)
      try {
        // Check campaign first to validate it's ready to play
        const campaignData = await api.get<Campaign>(`/campaigns/${campaignId}`)
        setCampaign(campaignData)

        if (campaignData.status !== 'active') {
          // Campaign not ready — redirect to setup lobby
          navigate(`/lobby/${campaignId}`, { replace: true })
          return
        }

        // Fetch the current (already-started) session — Lobby handles creation
        const sessionData = await api.get<{ id: string; init_status: string }>(
          `/campaigns/${campaignId}/sessions/current`,
        )
        setSessionId(sessionData.id)

        // Load characters first (needed to resolve character names in history)
        let charMap: Record<string, string> = {}
        try {
          const chars = await api.get<Character[]>(
            `/campaigns/${campaignId}/characters`,
          )
          setParty(chars)
          charMap = Object.fromEntries(chars.map((c) => [String(c.id), c.name]))
          const myChar = chars.find((c) => c.owner_id === String(user.id)) ?? chars[0]
          if (myChar) {
            setCharacter(myChar)
            setMyCharacter(myChar)
          }
          // Co-op: coleta TODOS os personagens do usuário logado
          const ownedChars = chars.filter((c) => c.owner_id === String(user.id))
          setMyCharacters(
            (ownedChars.length > 0 ? ownedChars : myChar ? [myChar] : []).map((c) => ({
              id: c.id,
              name: c.name,
            }))
          )
          setActiveMyCharIdx(0)
        } catch {
          // No character yet — that's OK
        }

        // Load full message history (includes gm_opening, player, ai_companion messages)
        try {
          const rawMessages = await api.get<Array<{
            id: string; role: string; content: string
            created_at: string; character_id?: string
          }>>(`/sessions/${sessionData.id}/messages`)

          setMessages(
            rawMessages.map((m) => ({
              id:             m.id,
              role:           m.role as ChatMessage['role'],
              content:        m.content,
              timestamp:      m.created_at,
              character_name: m.character_id ? (charMap[m.character_id] ?? undefined) : undefined,
            })),
          )
        } catch {
          // First session — no messages yet
        }

        // Restaura round ativo se existir (ex: GM está processando, ou collecting)
        try {
          const activeRound = await api.get<{
            round_id: string; round_number: number; status: string
            submitted_count: number; expected_count: number
            actions: Array<{
              character_name: string; is_ai: boolean; d20_roll: number
              initiative_order: number; action_text: string | null
              is_pass: boolean; character_id: string | null
            }>
          } | null>(`/rounds/active?session_id=${sessionData.id}`)

          if (activeRound) {
            const phase = activeRound.status as RoundPhase
            setRound({
              roundId:                activeRound.round_id,
              roundNumber:            activeRound.round_number,
              phase,
              submittedCount:         activeRound.submitted_count,
              expectedCount:          activeRound.expected_count || activeRound.submitted_count,
              submittedCharacterIds:  [],
              initiative:             phase !== 'collecting' ? activeRound.actions : [],
              gmResponses:            [],
            })
            // Se GM estava processando e serviço reiniciou, re-despacha
            if (phase === 'gm_processing') {
              api.post(`/rounds/${activeRound.round_id}/dispatch-gm`, {}).catch(() => {})
            }
          }
        } catch {
          // Nenhum round ativo — tudo bem
        }

        connect(sessionData.id, user.id)
      } catch {
        setMessages([
          {
            id:        crypto.randomUUID(),
            role:      'system',
            content:   'Falha ao conectar à sessão. Atualize a página.',
            timestamp: new Date().toISOString(),
          },
        ])
      } finally {
        setIsLoading(false)
      }
    }

    void loadSession()
    return () => disconnect()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, user?.id])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, gmTyping])

  // Fetch character portrait when active character changes
  useEffect(() => {
    if (!character?.id) { setCharacterImgUrl(null); return }
    let cancelled = false
    api.get<{ image_url: string }>(`/images/character/${character.id}`)
      .then((res) => { if (!cancelled) setCharacterImgUrl(res.image_url) })
      .catch(() => { if (!cancelled) setCharacterImgUrl(null) })
    return () => { cancelled = true }
  }, [character?.id])

  // ── Send action ───────────────────────────────────────────────────────────
  const sendAction = useCallback(async (text: string) => {
    if (!text.trim() || isSending || !sessionId) return

    const content = text.trim()
    setInputText('')
    setIsSending(true)

    // Optimistic player message
    const playerMsg: ChatMessage = {
      id:             crypto.randomUUID(),
      role:           'player',
      content,
      timestamp:      new Date().toISOString(),
      character_name: character?.name ?? user?.username,
    }
    setMessages((prev) => [...prev, playerMsg])
    setGmTyping(true)

    try {
      const action = {
        session_id:   sessionId,
        character_id: character?.id,
        action_text:  content,
      }
      send({ type: 'player_action', payload: action })
    } catch {
      setGmTyping(false)
      setMessages((prev) => [
        ...prev,
        {
          id:        crypto.randomUUID(),
          role:      'system',
          content:   'Failed to send your action. Please try again.',
          timestamp: new Date().toISOString(),
        },
      ])
    } finally {
      setIsSending(false)
      textareaRef.current?.focus()
    }
  }, [isSending, sessionId, character, user, send])

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendAction(inputText)
    }
  }

  // ── Round mode handlers ───────────────────────────────────────────────────
  const fetchAndSetActiveRound = useCallback(async (sid: string) => {
    try {
      const activeRound = await api.get<{
        round_id: string; round_number: number; status: string
        submitted_count: number; expected_count: number
        actions: Array<{
          character_name: string; is_ai: boolean; d20_roll: number
          initiative_order: number; action_text: string | null
          is_pass: boolean; character_id: string | null
        }>
      } | null>(`/rounds/active?session_id=${sid}`)

      if (activeRound) {
        const phase = activeRound.status as RoundPhase
        setRound({
          roundId:                activeRound.round_id,
          roundNumber:            activeRound.round_number,
          phase,
          submittedCount:         activeRound.submitted_count,
          expectedCount:          activeRound.expected_count || activeRound.submitted_count,
          submittedCharacterIds:  [],
          initiative:             phase !== 'collecting' ? activeRound.actions : [],
          gmResponses:            [],
        })
        if (phase === 'gm_processing') {
          api.post(`/rounds/${activeRound.round_id}/dispatch-gm`, {}).catch(() => {})
        }
      }
    } catch {
      // ignore
    }
  }, [])

  const startRound = useCallback(async () => {
    if (!sessionId || !campaignId) return
    setIsStartingRound(true)
    try {
      const result = await api.post<{
        round_id: string; round_number: number; expected_count: number; status: string
      }>('/rounds/start', { session_id: sessionId, campaign_id: campaignId })
      setRound({
        roundId:               result.round_id,
        roundNumber:           result.round_number,
        phase:                 result.status as RoundPhase,
        submittedCount:        0,
        expectedCount:         result.expected_count,
        submittedCharacterIds: [],
        initiative:            [],
        gmResponses:           [],
      })
    } catch (err: unknown) {
      // 409 = já existe round ativo → busca e exibe
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        await fetchAndSetActiveRound(sessionId)
      } else {
        const msg = err instanceof Error ? err.message : 'Erro ao iniciar round.'
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'system', content: msg, timestamp: new Date().toISOString() } as ChatMessage,
        ])
      }
    } finally {
      setIsStartingRound(false)
    }
  }, [sessionId, campaignId, fetchAndSetActiveRound])

  const handleRoundAction = useCallback((actionText: string | null, isPass: boolean) => {
    if (!sessionId || !campaignId) return
    // Co-op: usa o personagem ativo no switcher; fallback para myCharacter global
    const activeChar = myCharacters[activeMyCharIdx] ?? (myCharacter ? { id: myCharacter.id, name: myCharacter.name } : null)
    if (!activeChar) return
    send({
      type: 'submit_action',
      payload: {
        session_id:     sessionId,
        campaign_id:    campaignId,
        character_id:   activeChar.id,
        character_name: activeChar.name,
        is_pass:        isPass,
        action_text:    actionText,
        player_id:      user?.id,
      },
    })
    // Marca localmente como submetido (o WS action_submitted confirma depois)
    setRound((prev) => ({
      ...prev,
      submittedCharacterIds: [...new Set([...prev.submittedCharacterIds, activeChar.id])],
    }))
  }, [sessionId, campaignId, myCharacters, activeMyCharIdx, myCharacter, user, send])

  const toggleVoice = (): void => {
    setVoiceActive((current) => !current)
  }

  const difficultyLabel = campaign?.difficulty
    ? campaign.difficulty.charAt(0).toUpperCase() + campaign.difficulty.slice(1)
    : 'Normal'

  const sessionInfoText = campaign?.session_count
    ? `Sessão ${campaign.session_count} · ${campaign.status === 'active' ? 'Medium Campaign' : campaign.status}`
    : 'Sessão 1 · Campanha Active'

  const openSettings = (): void => {
    const result = window.prompt('Campaign settings (set difficulty: easy, normal, hard, hardcore)', 'difficulty:hard')
    if (!result) return
    const [, value] = result.split(':')
    const difficulty = value?.trim().toLowerCase()
    if (difficulty && ['easy', 'normal', 'hard', 'hardcore'].includes(difficulty)) {
      setCampaign((prev) => prev ? { ...prev, difficulty } : prev)
    }
  }

  const quickAction = (text: string): void => {
    setInputText(text)
    void sendAction(text)
  }

  // ── Render ────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Spinner size="lg" />
          <p className="text-amber-500 font-serif italic animate-pulse">
            The dungeon master prepares the scene…
          </p>
        </div>
      </div>
    )
  }

  return (
    <>
    {/* Kill modal — renderizado fora do layout principal para sobrepor tudo */}
    {currentKill && <KillModal event={currentKill} onClose={dismissKill} />}

    <div className="app">
      <header className="topbar">
        <div className="logo">
          <span className="logo-icon">⚔</span>
          Arcanum RPG
        </div>

        <div className="flex items-center gap-3">
          <div className="campaign-badge">{campaign?.title ?? 'The Shadow of Icewind Dale'}</div>
          <span className={`difficulty-badge diff-${campaign?.difficulty ?? 'normal'}`}>
            {difficultyLabel}
          </span>
          <div className="session-info">
            {sessionInfoText}
          </div>
        </div>

        <div className="topbar-right">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-amber-400 transition-colors px-2 py-1 rounded hover:bg-slate-700/50"
            title="Voltar ao Dashboard"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            Campanhas
          </button>
          <div className="difficulty-badge diff-normal" onClick={openSettings}>
            ⚙ Settings
          </div>
        </div>
      </header>

      <aside className="sidebar">
        <div className="sidebar-section">
          <h3>Party</h3>
          {party.length === 0 ? (
            <p className="text-slate-400 text-xs">Nenhum membro disponível ainda.</p>
          ) : (
            party.slice(0, 5).map((member) => {
              const isOwner = member.owner_id === String(user?.id)
              return (
                <div
                  key={member.id}
                  className={`char-card ${member.id === character?.id ? 'active' : ''}`}
                  onClick={() => setCharacter(member)}
                >
                  <div className="char-header">
                    <div className="char-avatar">{member.name?.slice(0, 2).toUpperCase()}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="char-name" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        {member.name}
                        {isOwner && (
                          <span style={{ fontSize: 9, background: '#78350f', color: '#fcd34d', borderRadius: 4, padding: '1px 5px', fontWeight: 700, letterSpacing: '0.05em', flexShrink: 0 }}>
                            VOCÊ
                          </span>
                        )}
                      </div>
                      <div className="char-meta">
                        {member.race ?? 'Unknown'} {member.character_class ?? ''} · Lv {member.level ?? 1}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>

        <AtmospherePanel
          mode={displayMode}
          enemies={combatEnemies}
          isLoading={sessionStateLoading}
        />

        <div className="sidebar-section" style={{ flex: 1 }}>
          <h3>World State</h3>
          <div className="text-slate-300 text-xs leading-relaxed bg-slate-900/80 border border-slate-800 rounded-xl p-3">
            {campaign?.description ?? 'Current scene: Abandoned watchtower, 3rd floor. Storm raging outside. A strange glyph pulses on the wall.'}
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="tabs">
          <div className={`tab ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
            ⚔ Game Session
          </div>
          <div className={`tab ${activeTab === 'sheet' ? 'active' : ''}`} onClick={() => setActiveTab('sheet')}>
            📜 Character Sheet
          </div>
          <div className={`tab ${activeTab === 'map' ? 'active' : ''}`} onClick={() => setActiveTab('map')}>
            🗺 World Map
          </div>
        </div>

        {activeTab === 'chat' && (
          <div className="chat-container">
            <div className="chat-wrap">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}

              {gmTyping && (
                <div className="gm-typing">
                  <div className="dot" />
                  <div className="dot" />
                  <div className="dot" />
                  <span>Arcanum is narrating...</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {useRoundMode ? (
              /* ── Modo de Round Coletivo ── */
              <RoundPanel
                round={round}
                myCharacters={
                  myCharacters.length > 0
                    ? myCharacters
                    : [{ id: myCharacter?.id ?? '', name: myCharacter?.name ?? character?.name ?? 'Aventureiro' }]
                }
                activeCharacterIdx={activeMyCharIdx}
                onChangeActiveCharacter={setActiveMyCharIdx}
                onSubmitAction={handleRoundAction}
                onStartRound={() => void startRound()}
                isStarting={isStartingRound}
              />
            ) : (
              /* ── Modo de Turno Livre (legado) ── */
              <div className="input-area">
                <div className="quick-actions">
                  {/* Toggle para modo round */}
                  <button
                    type="button"
                    className="quick-btn"
                    style={{ borderColor: 'var(--amber)', color: 'var(--amber)' }}
                    onClick={() => setUseRoundMode(true)}
                    title="Alternar para modo de round coletivo com d20"
                  >
                    🎲 Round
                  </button>
                  <button type="button" className="quick-btn" onClick={() => quickAction('I attack!')}>⚔ Attack</button>
                  <button type="button" className="quick-btn" onClick={() => quickAction('I search the area carefully.')}>🔍 Search</button>
                  <button type="button" className="quick-btn" onClick={() => quickAction('I try to persuade the NPC.')}>💬 Persuade</button>
                  <button type="button" className="quick-btn" onClick={() => quickAction('I take a short rest.')}>🛌 Short Rest</button>
                  <button type="button" className="quick-btn" onClick={() => quickAction('I use stealth to hide.')}>👁 Stealth</button>
                  <button type="button" className="quick-btn" onClick={() => quickAction('OOC: What are our options here?')}>💭 OOC</button>
                </div>
                <div className="input-row">
                  <button type="button" className={`voice-btn ${voiceActive ? 'active' : ''}`} onClick={toggleVoice}>
                    {voiceActive ? '⏹' : '🎙'}
                  </button>
                  <textarea
                    ref={textareaRef}
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onInput={(e) => {
                      const el = e.currentTarget
                      el.style.height = 'auto'
                      el.style.height = `${Math.min(el.scrollHeight, 128)}px`
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder="What do you do? Speak or type your action..."
                    className="input-box"
                    rows={1}
                  />
                  <button type="button" className="send-btn" onClick={() => void sendAction(inputText)}>
                    ➤
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'sheet' && (
          <div id="tab-sheet" className="sheet-wrap">
            <div className="stat-card" style={{ gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '14px' }}>
                <div className="char-avatar" style={{ width: 52, height: 52, fontSize: 20 }}>{character?.name?.slice(0, 2).toUpperCase()}</div>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text1)' }}>{character?.name ?? 'Adventurer'}</div>
                  <div style={{ fontSize: 13, color: 'var(--text3)' }}>
                    {character?.race ?? 'Unknown'} {character?.character_class ?? 'Class'} · Level {character?.level ?? 1}
                  </div>
                </div>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: '12px' }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>AC</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--teal)' }}>{character?.attributes?.armor_class ?? 10}</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>Speed</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text1)' }}>{character?.attributes?.speed ?? 30}</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>Initiative</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--gold)' }}>+{character?.attributes?.dexterity ?? 2}</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="stat-card">
              <h4>Ability Scores</h4>
              <div className="stat-grid">
                {['STR','DEX','CON','INT','WIS','CHA'].map((key) => (
                  <div key={key} className="stat-box">
                    <div className="stat-name">{key}</div>
                    <div className="stat-val">{character?.attributes?.[key.toLowerCase() as keyof Character['attributes']] ?? 10}</div>
                    <div className="stat-mod">+{Math.floor(((character?.attributes?.[key.toLowerCase() as keyof Character['attributes']] ?? 10) - 10) / 2)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="stat-card">
              <h4>Inventory</h4>
              {(character?.inventory.length ?? 0) === 0 ? (
                <p className="text-slate-400 text-sm">No inventory items available.</p>
              ) : (
                character?.inventory.slice(0, 6).map((item) => (
                  <div key={item.id} className="inventory-row">
                    <span className="item-name">{item.item_name}</span>
                    <span className="item-type">{item.item_type}{item.equipped ? ' (E)' : ''}</span>
                    <span className="item-qty">{item.quantity ?? 1}</span>
                  </div>
                ))
              )}
            </div>

            <div className="stat-card">
              <h4>Spell Slots / Resources</h4>
              <div className="flex flex-wrap gap-3">
                {Object.entries(character?.status?.spell_slots ?? { '1': 2, '2': 1 }).map(([level, count]) => (
                  <div key={level} className="badge badge-warning">
                    Lv {level}: {count} slots
                  </div>
                ))}
              </div>
              <div className="mt-3 text-slate-400 text-xs">
                Superior dice and spell resources are tracked by the GM during gameplay.
              </div>
            </div>
          </div>
        )}

        {activeTab === 'map' && (
          <div id="tab-map" className="map-wrap">
            <WorldMap
              campaignId={campaignId ?? ''}
              onLocationSelect={(name) => void sendAction(`Vou até ${name}`)}
            />
          </div>
        )}
      </main>

      {/* ── Character side panels (direita) ─────────────────────── */}
      <div className="char-panels">
        {/* Box 1 — portrait */}
        <div className="char-panel-img">
          <div className="text-[9px] text-slate-500 uppercase tracking-widest mb-2">
            {character?.name ?? 'Personagem'}
          </div>
          {characterImgUrl ? (
            <img
              src={characterImgUrl}
              alt={character?.name ?? 'Personagem'}
              className="w-full aspect-square object-cover rounded-lg border border-slate-700"
            />
          ) : (
            <div className="pixel-placeholder">
              {character?.char_type === 'ai_companion' ? '🤖' : '🧙'}
            </div>
          )}
          <div className="text-[10px] text-slate-400 mt-2 text-center leading-tight">
            {character?.race ?? '—'} {character?.character_class ?? '—'}
          </div>
          <div className="text-[10px] text-amber-400 mt-0.5">Lv {character?.level ?? 1}</div>
        </div>

        {/* Box 2 — stats */}
        <div className="char-panel-stats">
          {(() => {
            const hpCur = character?.status?.hp_current ?? 0
            const hpMax = character?.status?.hp_max ?? 1
            const hpPct = Math.max(0, Math.min(100, (hpCur / hpMax) * 100))
            const hpClr = hpPct > 50 ? '#22c55e' : hpPct > 25 ? '#f59e0b' : '#ef4444'
            const attrs = character?.attributes
            const modOf = (v: number) => { const m = Math.floor((v - 10) / 2); return m >= 0 ? `+${m}` : `${m}` }
            return (
              <>
                <div className="cstat-row">
                  <span className="cstat-label">HP</span>
                  <span className="cstat-value">{hpCur}/{hpMax}</span>
                </div>
                <div className="cstat-hp-bar">
                  <div className="cstat-hp-fill" style={{ width: `${hpPct}%`, background: hpClr }} />
                </div>
                <div className="cstat-row">
                  <span className="cstat-label">AC</span>
                  <span className="cstat-value">{attrs?.armor_class ?? 10}</span>
                </div>
                <div className="cstat-row">
                  <span className="cstat-label">Init</span>
                  <span className="cstat-value">{modOf(attrs?.dexterity ?? 10)}</span>
                </div>
                <div className="cstat-row">
                  <span className="cstat-label">Speed</span>
                  <span className="cstat-value">{attrs?.speed ?? 30}ft</span>
                </div>
                <div className="cstat-row">
                  <span className="cstat-label">Prof</span>
                  <span className="cstat-value">+{character?.proficiency_bonus ?? 2}</span>
                </div>
                <div className="cstat-divider" />
                <div className="text-[9px] text-slate-500 uppercase tracking-widest mb-1">Atributos</div>
                <div className="cstat-attr-grid">
                  {(['strength','dexterity','constitution','intelligence','wisdom','charisma'] as const).map((key) => (
                    <div key={key} className="cstat-attr-box">
                      <span className="cstat-attr-name">{key.slice(0,3).toUpperCase()}</span>
                      <span className="cstat-attr-val">{attrs?.[key] ?? 10}</span>
                      <span className="cstat-attr-mod">{modOf(attrs?.[key] ?? 10)}</span>
                    </div>
                  ))}
                </div>
                {(character?.status?.conditions ?? []).length > 0 && (
                  <>
                    <div className="cstat-divider" />
                    <div className="flex flex-wrap gap-1">
                      {character!.status!.conditions.map((c) => (
                        <span key={c} className="condition-tag">{c}</span>
                      ))}
                    </div>
                  </>
                )}
              </>
            )
          })()}
        </div>
      </div>
    </div>
    </>
  )
}
