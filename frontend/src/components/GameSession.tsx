import React, {
  useState, useEffect, useRef, useCallback, KeyboardEvent
} from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Send, Wifi, WifiOff, AlertTriangle, Users,
  Map, BookOpen, ChevronLeft, Dice1, Dice6, Volume2,
  Image as ImageIcon, Heart, Shield, Zap, X
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { useWebSocket } from '../hooks/useWebSocket'
import { Spinner } from './ui/Spinner'
import { Badge } from './ui/Badge'
import type {
  ChatMessage, Character, CharacterStatus, WSMessage,
  GMResponse, PlayerAction, DiceRoll, StateUpdate, Campaign
} from '../types'
import WorldMap from './WorldMap'

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

// ─── Dice result display ───────────────────────────────────────────────────
function DiceRollDisplay({ roll }: { roll: DiceRoll }): React.ReactElement {
  const isCrit  = roll.notation.includes('d20') && roll.result === 20
  const isFumble = roll.notation.includes('d20') && roll.result === 1

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold font-serif border ${
      isCrit
        ? 'bg-amber-900/60 border-amber-500/60 text-amber-300 shadow-amber'
        : isFumble
        ? 'bg-red-900/60 border-red-500/60 text-red-300'
        : 'bg-slate-700/60 border-slate-600/60 text-slate-300'
    }`}>
      {isCrit ? <Dice6 className="w-3 h-3 text-amber-400" /> : <Dice1 className="w-3 h-3 text-slate-400" />}
      {roll.notation} = <strong>{roll.result}</strong>
      {roll.breakdown && <span className="text-slate-400 font-normal">({roll.breakdown})</span>}
    </span>
  )
}

// ─── State update display ──────────────────────────────────────────────────
function StateUpdateDisplay({ update }: { update: StateUpdate }): React.ReactElement {
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-purple-900/40 border border-purple-700/40 rounded px-2 py-0.5 text-purple-300">
      <Zap className="w-3 h-3" />
      {update.label}
    </span>
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

  const timeStr = new Date(message.timestamp).toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit',
  })

  if (message.role === 'system') {
    return (
      <div className="flex justify-center my-2 animate-fade-in">
        <div className="chat-system max-w-lg text-center">
          {message.content}
        </div>
      </div>
    )
  }

  const isGM     = message.role === 'gm'
  const isPlayer = message.role === 'player'

  return (
    <div className={`flex flex-col gap-1 animate-fade-in ${isPlayer ? 'items-end' : 'items-start'}`}>
      {/* Sender label */}
      <div className={`flex items-center gap-1.5 text-xs ${isGM ? 'text-amber-500' : 'text-blue-400'}`}>
        {isGM && <span className="font-serif font-semibold tracking-wide">Dungeon Master</span>}
        {isPlayer && (
          <>
            <span className="font-serif">{message.character_name ?? 'You'}</span>
          </>
        )}
        <span className="text-slate-600">{timeStr}</span>
      </div>

      {/* Bubble */}
      <div className={`max-w-[85%] ${isGM ? 'chat-gm' : 'chat-player'}`}>
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>

        {/* Dice rolls */}
        {message.dice_rolls && message.dice_rolls.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-slate-700/40">
            {message.dice_rolls.map((roll, i) => (
              <DiceRollDisplay key={i} roll={roll} />
            ))}
          </div>
        )}

        {/* State updates */}
        {message.state_updates && message.state_updates.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {message.state_updates.map((upd, i) => (
              <StateUpdateDisplay key={i} update={upd} />
            ))}
          </div>
        )}

        {/* Image */}
        {message.image_url && (
          <div className="mt-3 rounded-lg overflow-hidden border border-amber-700/30">
            <img
              src={message.image_url}
              alt="Scene illustration"
              className="w-full object-cover max-h-64"
              loading="lazy"
            />
            <p className="text-xs text-center text-amber-700/60 py-1 flex items-center justify-center gap-1">
              <ImageIcon className="w-3 h-3" /> AI-generated scene
            </p>
          </div>
        )}

        {/* Audio indicator */}
        {message.audio_url && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-amber-500">
            <Volume2 className={`w-3.5 h-3.5 ${audioPlaying ? 'animate-pulse' : ''}`} />
            {audioPlaying ? 'Playing narration…' : 'Narration played'}
          </div>
        )}
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
  const { status } = character
  const hpPercent  = Math.max(0, Math.min(100, (status.hp_current / status.hp_max) * 100))
  const hpColor    = hpPercent > 50 ? 'bg-green-600' : hpPercent > 25 ? 'bg-amber-500' : 'bg-red-600'

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
            {status.hp_current}{status.hp_temp > 0 && <span className="text-blue-400">+{status.hp_temp}</span>} / {status.hp_max}
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
          <Shield className="w-3 h-3 text-blue-400" /> AC {status.ac}
        </span>
        <span className="flex items-center gap-1 text-slate-400">
          <Zap className="w-3 h-3 text-amber-400" /> {status.speed} ft
        </span>
      </div>

      {/* Conditions */}
      {status.conditions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {status.conditions.map((c) => (
            <span key={c} className="badge-condition">{c}</span>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Main GameSession component ────────────────────────────────────────────
export default function GameSession(): React.ReactElement {
  const { id: campaignId } = useParams<{ id: string }>()
  const { user }           = useAuth()

  const [campaign,        setCampaign]        = useState<Campaign | null>(null)
  const [character,       setCharacter]       = useState<Character | null>(null)
  const [sessionId,       setSessionId]       = useState<number | null>(null)
  const [messages,        setMessages]        = useState<ChatMessage[]>([])
  const [inputText,       setInputText]       = useState('')
  const [isSending,       setIsSending]       = useState(false)
  const [isLoading,       setIsLoading]       = useState(true)
  const [gateBlocked,     setGateBlocked]     = useState(false)
  const [showMap,         setShowMap]         = useState(false)
  const [gmTyping,        setGmTyping]        = useState(false)

  const messagesEndRef    = useRef<HTMLDivElement>(null)
  const textareaRef       = useRef<HTMLTextAreaElement>(null)

  // ── WebSocket ────────────────────────────────────────────────────────────
  const handleWsMessage = useCallback((wsMsg: WSMessage) => {
    switch (wsMsg.type) {
      case 'gm_response': {
        const gm = wsMsg.payload as GMResponse
        setGmTyping(false)
        setMessages((prev) => [
          ...prev,
          {
            id:            crypto.randomUUID(),
            role:          'gm',
            content:       gm.content,
            timestamp:     gm.timestamp,
            dice_rolls:    gm.dice_rolls,
            state_updates: gm.state_updates,
            image_url:     gm.image_url,
            audio_url:     gm.audio_url,
          } as ChatMessage,
        ])
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
      default:
        break
    }
  }, [])

  const { connect, disconnect, send, connectionStatus } = useWebSocket({
    onMessage: handleWsMessage,
  })

  // ── Initial load ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!campaignId || !user) return

    const loadSession = async () => {
      setIsLoading(true)
      try {
        const [campaignData, sessionData] = await Promise.all([
          api.get<Campaign>(`/campaigns/${campaignId}`),
          api.post<{ id: number; history: ChatMessage[] }>(
            `/campaigns/${campaignId}/sessions/start`,
          ),
        ])
        setCampaign(campaignData)
        setSessionId(sessionData.id)
        setMessages(sessionData.history ?? [])

        // Load character
        try {
          const chars = await api.get<Character[]>(
            `/campaigns/${campaignId}/characters?player_id=${user.id}`,
          )
          if (chars.length > 0) setCharacter(chars[0])
        } catch {
          // No character yet — that's OK
        }

        connect(sessionData.id, user.id)
      } catch {
        setMessages([
          {
            id:        crypto.randomUUID(),
            role:      'system',
            content:   'Failed to connect to the session. Please refresh.',
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
      const action: Partial<PlayerAction> = {
        session_id:   sessionId,
        character_id: character?.id,
        content,
        action_type:  'free_action',
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
    <div className="h-screen bg-slate-900 flex flex-col overflow-hidden">
      {/* ── Header ── */}
      <header className="bg-slate-900/95 backdrop-blur border-b border-amber-700/30 px-4 py-2.5 flex items-center justify-between shrink-0 z-30">
        <div className="flex items-center gap-3">
          <Link to="/dashboard" className="btn-ghost py-1 px-2 text-xs">
            <ChevronLeft className="w-3.5 h-3.5" />
          </Link>
          <div>
            <h1 className="font-serif text-amber-400 text-sm font-semibold leading-none">
              {campaign?.title ?? 'Session'}
            </h1>
            <p className="text-slate-500 text-xs mt-0.5">{campaign?.rpg_system}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <ConnectionBadge status={connectionStatus} />
          <div className="w-px h-4 bg-slate-700" />
          <Link
            to={`/campaign/${campaignId}/characters`}
            className="btn-ghost py-1 px-2 text-xs"
            title="Characters"
          >
            <Users className="w-3.5 h-3.5" />
          </Link>
          <button
            onClick={() => setShowMap((v) => !v)}
            className={`btn-ghost py-1 px-2 text-xs ${showMap ? 'border-amber-600/60 text-amber-400' : ''}`}
            title="World Map"
          >
            <Map className="w-3.5 h-3.5" />
          </button>
          <Link to="/knowledge" className="btn-ghost py-1 px-2 text-xs" title="Knowledge Bank">
            <BookOpen className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      {/* ── Gate blocked banner ── */}
      {gateBlocked && (
        <div className="bg-red-900/50 border-b border-red-700/60 px-4 py-2 flex items-center gap-2 text-red-300 text-xs shrink-0">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>
            The GM needs knowledge to continue.{' '}
            <Link to="/knowledge" className="underline hover:text-red-200">
              Upload a rulebook
            </Link>{' '}
            to unlock the session.
          </span>
          <button onClick={() => setGateBlocked(false)} className="ml-auto hover:text-red-200">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ── Main area ── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: character status (hidden on mobile) */}
        {character && (
          <aside className="hidden lg:flex flex-col w-64 border-r border-amber-700/20 p-3 gap-3 overflow-y-auto bg-slate-900/60 shrink-0">
            <CharStatusPanel
              character={character}
              onExpand={() => window.open(`/campaign/${campaignId}/characters`, '_blank')}
            />
          </aside>
        )}

        {/* Center: chat */}
        <div className="flex flex-col flex-1 overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                <div className="w-16 h-16 bg-amber-900/20 rounded-full flex items-center justify-center border border-amber-700/30">
                  <Dice6 className="w-8 h-8 text-amber-700/60" />
                </div>
                <div>
                  <p className="text-slate-300 font-serif italic text-sm">
                    The adventure awaits…
                  </p>
                  <p className="text-slate-500 text-xs mt-1">
                    Describe your action to begin the session.
                  </p>
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* GM typing indicator */}
            {gmTyping && (
              <div className="flex items-center gap-2 animate-fade-in">
                <div className="chat-gm flex items-center gap-2">
                  <div className="flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <div
                        key={i}
                        className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </div>
                  <span className="text-amber-600/70 text-xs font-serif italic">
                    The GM is narrating…
                  </span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div className="border-t border-amber-700/20 bg-slate-900/90 p-3 shrink-0">
            <div className="flex gap-2 items-end">
              <textarea
                ref={textareaRef}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe your action… (Enter to send, Shift+Enter for new line)"
                className="input-dark flex-1 resize-none min-h-[44px] max-h-32 leading-relaxed py-2.5"
                rows={1}
                disabled={isSending || connectionStatus !== 'connected'}
                style={{ height: 'auto' }}
                onInput={(e) => {
                  const el = e.currentTarget
                  el.style.height = 'auto'
                  el.style.height = Math.min(el.scrollHeight, 128) + 'px'
                }}
              />
              <button
                onClick={() => void sendAction(inputText)}
                disabled={
                  !inputText.trim() ||
                  isSending ||
                  connectionStatus !== 'connected'
                }
                className="btn-primary px-3 py-2.5 shrink-0"
                title="Send action (Enter)"
              >
                {isSending ? (
                  <Spinner size="sm" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
            <p className="text-slate-700 text-xs mt-1.5 text-right">
              Enter to send · Shift+Enter for new line
            </p>
          </div>
        </div>

        {/* Right panel: World Map (toggleable) */}
        {showMap && (
          <aside className="hidden xl:flex flex-col w-72 border-l border-amber-700/20 bg-slate-900/60 shrink-0">
            <WorldMap
              campaignId={campaignId ?? ''}
              onLocationSelect={(name) => void sendAction(`Vou até ${name}`)}
            />
          </aside>
        )}
      </div>
    </div>
  )
}
