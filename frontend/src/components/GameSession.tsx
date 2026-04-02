import React, {
  useState, useEffect, useRef, useCallback, KeyboardEvent
} from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
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
  DiceRoll, StateUpdate, Campaign
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

  // ── Opening narration — special immersive card ─────────────────────────
  if (message.role === 'gm_opening') {
    return (
      <div className="my-4 animate-fade-in">
        <div className="relative border border-amber-700/50 bg-gradient-to-b from-amber-950/30 to-slate-900/60 rounded-xl p-5 shadow-lg">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-4 h-4 text-amber-400" />
            <span className="text-amber-400 font-serif text-xs font-semibold tracking-widest uppercase">Abertura da Campanha</span>
            <span className="text-slate-600 text-xs ml-auto">{timeStr}</span>
          </div>
          <p className="text-slate-200 font-serif leading-relaxed whitespace-pre-wrap italic">
            {message.content}
          </p>
        </div>
      </div>
    )
  }

  // ── AI Companion reaction ───────────────────────────────────────────────
  if (message.role === 'ai_companion') {
    return (
      <div className="flex flex-col gap-1 animate-fade-in items-start">
        <div className="flex items-center gap-1.5 text-xs text-purple-400">
          <span className="font-serif">{message.character_name ?? 'Companion'}</span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-900/50 border border-purple-700/50 text-purple-300">IA</span>
          <span className="text-slate-600">{timeStr}</span>
        </div>
        <div className="max-w-[80%] bg-purple-950/40 border border-purple-800/40 rounded-lg px-4 py-2.5 text-slate-300 text-sm font-serif italic">
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

// ─── Main GameSession component ────────────────────────────────────────────
export default function GameSession(): React.ReactElement {
  const { id: campaignId } = useParams<{ id: string }>()
  const { user }           = useAuth()
  const navigate           = useNavigate()

  const [campaign,        setCampaign]        = useState<Campaign | null>(null)
  const [character,       setCharacter]       = useState<Character | null>(null)
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

  const messagesEndRef    = useRef<HTMLDivElement>(null)
  const textareaRef       = useRef<HTMLTextAreaElement>(null)

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

        // Load full message history (includes gm_opening + ai_companion messages)
        try {
          const rawMessages = await api.get<Array<{
            id: string; role: string; content: string
            created_at: string; character_id?: string
          }>>(`/sessions/${sessionData.id}/messages`)

          setMessages(
            rawMessages.map((m) => ({
              id:        m.id,
              role:      m.role as ChatMessage['role'],
              content:   m.content,
              timestamp: m.created_at,
            })),
          )
        } catch {
          // First session — no messages yet
        }

        // Load character
        try {
          const chars = await api.get<Character[]>(
            `/campaigns/${campaignId}/characters`,
          )
          setParty(chars)
          const myChar = chars.find((c) => c.owner_id === String(user.id)) ?? chars[0]
          if (myChar) setCharacter(myChar)
        } catch {
          // No character yet — that's OK
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
            party.slice(0, 5).map((member) => (
              <div
                key={member.id}
                className={`char-card ${member.id === character?.id ? 'active' : ''}`}
                onClick={() => setCharacter(member)}
              >
                <div className="char-header">
                  <div className="char-avatar">{member.name?.slice(0, 2).toUpperCase()}</div>
                  <div>
                    <div className="char-name">{member.name}</div>
                    <div className="char-meta">
                      {member.race ?? 'Unknown'} {member.character_class ?? ''} · Lv {member.level ?? 1}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="sidebar-section">
          <h3>Active Quests</h3>
          <div className="quest-item">
            <div className="quest-title">Recover the lost grimoire</div>
            <div className="quest-sub">Find Valindra's spellbook before the watchers break through.</div>
          </div>
          <div className="quest-item">
            <div className="quest-title">Protect Bryn Shander</div>
            <div className="quest-sub">Hold the line against the winter wolves.</div>
          </div>
          <div className="quest-item complete">
            <div className="quest-title">Delivered supplies</div>
            <div className="quest-sub">Bremen is secure for now.</div>
          </div>
        </div>

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

            <div className="input-area">
              <div className="quick-actions">
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
        {/* Box 1 — portrait 8-bit */}
        <div className="char-panel-img">
          <div className="text-[9px] text-slate-500 uppercase tracking-widest mb-2">
            {character?.name ?? 'Personagem'}
          </div>
          <div className="pixel-placeholder">
            {character?.char_type === 'ai_companion' ? '🤖' : '🧙'}
          </div>
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
  )
}
