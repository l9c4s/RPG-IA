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
        // Check campaign first to validate it's ready to play
        const campaignData = await api.get<Campaign>(`/campaigns/${campaignId}`)
        setCampaign(campaignData)

        if (campaignData.status !== 'active') {
          // Campaign not ready — redirect to setup lobby
          navigate(`/lobby/${campaignId}`, { replace: true })
          return
        }

        const sessionData = await api.post<{ id: string; history: ChatMessage[] }>(
          `/campaigns/${campaignId}/sessions/start`,
        )
        setSessionId(sessionData.id)
        setMessages(sessionData.history ?? [])

        // Load character
        try {
          const chars = await api.get<Character[]>(
            `/campaigns/${campaignId}/characters`,
          )
          setParty(chars)
          const myChar = chars.find((c) => c.player_id === String(user.id)) ?? chars[0]
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
            party.slice(0, 5).map((member, index) => {
              const hpMax = member.status?.hp_max ?? 1
              const hpCur = member.status?.hp_current ?? 0
              const hpPercent = Math.max(0, Math.min(100, (hpCur / hpMax) * 100))
              const hpColor = hpPercent > 50 ? 'hp-full' : hpPercent > 25 ? 'hp-mid' : 'hp-low'

              return (
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
                  <div className="hp-bar-wrap">
                    <div className="hp-label"><span>HP</span><span>{hpCur}/{hpMax}</span></div>
                    <div className="hp-bar"><div className={`hp-fill ${hpColor}`} style={{ width: `${hpPercent}%` }} /></div>
                  </div>
                  {(member.status?.conditions ?? []).length > 0 && (
                    <div className="conditions">
                      {member.status?.conditions.map((cond) => (
                        <span key={cond} className="condition-tag">{cond}</span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })
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
              <div className="hp-bar-wrap" style={{ marginTop: 8 }}>
                <div className="hp-label"><span style={{ fontWeight: 600 }}>Hit Points</span><span style={{ fontWeight: 700, color: 'var(--gold)' }}>{character?.status?.hp_current ?? 0} / {character?.status?.hp_max ?? 0}</span></div>
                <div className="hp-bar" style={{ height: 10 }}><div className={`hp-fill ${character?.status?.hp_current && character?.status?.hp_max ? (character.status.hp_current / character.status.hp_max) > 0.5 ? 'hp-full' : (character.status.hp_current / character.status.hp_max) > 0.25 ? 'hp-mid' : 'hp-low' : 'hp-low'}`} style={{ width: `${character?.status?.hp_max ? Math.max(0, Math.min(100, (character.status.hp_current / character.status.hp_max) * 100)) : 0}%` }} /></div>
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
                    <span className="item-name">{item.name}</span>
                    <span className="item-type">{item.description ?? (item.equipped ? 'equipped' : 'item')}</span>
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
    </div>
  )
}
