import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Sword, Users, Plus, AlertCircle, ChevronLeft, Eye, Play,
  Loader2, BookOpen, Map, CheckCircle, XCircle,
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { AppLayout } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import CharacterCreationModal from '../components/CharacterCreationModal'
import type { Campaign, Character } from '../types'

type InitStatus = 'idle' | 'generating' | 'ready' | 'failed'

interface SessionInfo {
  id:           string
  campaign_id:  string
  started_at:   string
  init_status:  InitStatus
  has_opening:  boolean
}

// ── Init-progress stepper ─────────────────────────────────────────────────
const STEPS: { key: InitStatus | 'start'; label: string; icon: React.ReactNode }[] = [
  { key: 'start',      label: 'Sessão criada',         icon: <CheckCircle  className="w-4 h-4" /> },
  { key: 'generating', label: 'Gerando história…',     icon: <BookOpen     className="w-4 h-4" /> },
  { key: 'ready',      label: 'Mapa e abertura prontos', icon: <Map         className="w-4 h-4" /> },
]

function InitStepper({ status }: { status: InitStatus }): React.ReactElement {
  const activeIdx = status === 'ready' ? 2 : status === 'generating' ? 1 : 0

  return (
    <div className="card-rune p-6">
      <div className="flex items-center gap-2 mb-5">
        <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />
        <h2 className="font-serif text-amber-400 text-lg">Preparando a aventura…</h2>
      </div>

      <div className="space-y-3">
        {STEPS.map(({ label, icon }, idx) => {
          const done    = idx < activeIdx || status === 'ready'
          const current = idx === activeIdx && status !== 'ready'
          return (
            <div key={idx} className={`flex items-center gap-3 text-sm transition-colors ${
              done    ? 'text-amber-400' :
              current ? 'text-slate-200' :
                        'text-slate-600'
            }`}>
              <span className={`shrink-0 ${done ? 'text-amber-400' : current ? 'text-amber-500' : 'text-slate-700'}`}>
                {done ? <CheckCircle className="w-4 h-4" /> : icon}
              </span>
              <span className="font-serif">{label}</span>
              {current && (
                <span className="ml-auto flex gap-1">
                  {[0,1,2].map(i => (
                    <span key={i} className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" style={{ animationDelay: `${i * 150}ms` }} />
                  ))}
                </span>
              )}
            </div>
          )
        })}
      </div>

      {status === 'failed' && (
        <div className="flex items-center gap-2 mt-4 text-red-300 text-sm">
          <XCircle className="w-4 h-4 shrink-0" />
          Falha ao gerar abertura. Você pode entrar assim mesmo.
        </div>
      )}
    </div>
  )
}

export default function Lobby(): React.ReactElement {
  const { id: campaignId }         = useParams<{ id: string }>()
  const { user }                   = useAuth()
  const navigate                   = useNavigate()

  const [campaign,         setCampaign]         = useState<Campaign | null>(null)
  const [characters,       setCharacters]       = useState<Character[]>([])
  const [session,          setSession]          = useState<SessionInfo | null>(null)
  const [isLoading,        setIsLoading]        = useState(true)
  const [isStarting,       setIsStarting]       = useState(false)
  const [startError,       setStartError]       = useState<string | null>(null)
  const [error,            setError]            = useState<string | null>(null)
  const [showCreateModal,  setShowCreateModal]  = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = useCallback(async () => {
    if (!campaignId) return
    setIsLoading(true)
    setError(null)
    try {
      const [campaignData, charData] = await Promise.all([
        api.get<Campaign>(`/campaigns/${campaignId}`),
        api.get<Character[]>(`/campaigns/${campaignId}/characters`),
      ])
      setCampaign(campaignData)
      setCharacters(charData)

      // Verificar se já existe sessão iniciada (404 = sem sessão, não é erro)
      try {
        const sessionData = await api.get<SessionInfo>(`/campaigns/${campaignId}/sessions/current`)
        setSession(sessionData)
      } catch {
        setSession(null)
      }
    } catch {
      setError('Failed to load lobby data.')
    } finally {
      setIsLoading(false)
    }
  }, [campaignId])

  useEffect(() => { void fetchData() }, [fetchData])

  // Poll every 3 s while the opening flow is running
  useEffect(() => {
    if (!campaignId || !session || session.init_status !== 'generating') {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      return
    }
    pollRef.current = setInterval(async () => {
      try {
        const updated = await api.get<SessionInfo>(`/campaigns/${campaignId}/sessions/current`)
        setSession(updated)
        if (updated.init_status !== 'generating') {
          clearInterval(pollRef.current!)
          pollRef.current = null
          if (updated.init_status === 'ready') {
            navigate(`/campaign/${campaignId}`)
          }
        }
      } catch { /* ignore transient poll errors */ }
    }, 3000)
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }
  }, [campaignId, session?.init_status]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleStartSession = async () => {
    if (!campaignId) return
    setIsStarting(true)
    setStartError(null)
    try {
      const sessionData = await api.post<SessionInfo>(`/campaigns/${campaignId}/sessions/start`, {})
      setSession(sessionData)
      // Atualiza status da campanha localmente
      setCampaign((prev) => prev ? { ...prev, status: 'active' } : prev)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao iniciar a sessão.'
      setStartError(msg)
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <AppLayout>
      {/* Back navigation */}
      <div className="mb-6">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ChevronLeft className="w-3.5 h-3.5" />}
          onClick={() => navigate('/dashboard')}
        >
          Dashboard
        </Button>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Spinner size="lg" />
          <p className="text-slate-400 font-serif italic text-sm">
            Preparing the keep…
          </p>
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 bg-red-900/40 border border-red-700/60 rounded-lg px-5 py-4 text-red-300 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
          <button
            onClick={fetchData}
            className="ml-auto text-xs underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      ) : campaign ? (
        <div className="space-y-6 max-w-3xl mx-auto">
          {/* Campaign header */}
          <div className="card-rune p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-serif text-amber-400 mb-1">
                  {campaign.title}
                </h1>
                <p className="text-slate-400 text-sm font-serif">{campaign.rpg_system}</p>
                {campaign.description && (
                  <p className="text-slate-300 text-sm italic mt-2 leading-relaxed">
                    {campaign.description}
                  </p>
                )}
              </div>
              <Badge
                variant={
                  campaign.status === 'active'    ? 'success' :
                  campaign.status === 'paused'    ? 'warning' :
                  campaign.status === 'completed' ? 'info'    : 'danger'
                }
                className="shrink-0"
              >
                {campaign.status}
              </Badge>
            </div>
          </div>

          {/* Players */}
          <div className="card-rune p-6">
            <div className="flex items-center gap-2 mb-4">
              <Users className="w-4 h-4 text-amber-500" />
              <h2 className="font-serif text-amber-400 text-lg">
                Party Members
              </h2>
            </div>

            {characters.length === 0 ? (
              <p className="text-slate-500 font-serif italic text-sm">
                No characters in this campaign yet.
              </p>
            ) : (
              <div className="space-y-3">
                {characters.map((char) => (
                  <div
                    key={char.id}
                    className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg border border-slate-700/40"
                  >
                    <div>
                      <p className="text-slate-200 font-semibold text-sm">{char.name}</p>
                      <p className="text-slate-500 text-xs">
                        Level {char.level} {char.character_class} · {char.race}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {char.owner_id === String(user?.id) && (
                        <Badge variant="success">You</Badge>
                      )}
                      <span className="text-slate-400 text-xs">
                        HP {char.status?.hp_current ?? 0}/{char.status?.hp_max ?? 0}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Opening-flow progress stepper */}
          {session && session.init_status !== 'idle' && (
            <InitStepper status={session.init_status} />
          )}

          {/* Avisos */}
          {characters.length === 0 && (
            <div className="flex items-center gap-2 bg-amber-900/30 border border-amber-700/50 rounded-lg px-4 py-3 text-amber-300 text-sm font-serif italic">
              <AlertCircle className="w-4 h-4 shrink-0" />
              Crie pelo menos 1 personagem para iniciar a sessão.
            </div>
          )}
          {startError && (
            <div className="flex items-center gap-2 bg-red-900/40 border border-red-700/60 rounded-lg px-4 py-3 text-red-300 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {startError}
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3">
            {session ? (
              /* Sessão já iniciada — aguardar abertura ou entrar */
              <Button
                variant="primary"
                leftIcon={
                  session.init_status === 'generating'
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <Sword className="w-4 h-4" />
                }
                onClick={() => navigate(`/campaign/${campaignId}`)}
                disabled={session.init_status === 'generating'}
                className="flex-1 justify-center"
              >
                {session.init_status === 'generating' ? 'Preparando…' : 'Entrar na Sessão'}
              </Button>
            ) : (
              /* Sessão ainda não iniciada — iniciar */
              <Button
                variant="primary"
                leftIcon={<Play className="w-4 h-4" />}
                onClick={() => void handleStartSession()}
                isLoading={isStarting}
                disabled={characters.length === 0}
                className="flex-1 justify-center"
              >
                Iniciar Sessão
              </Button>
            )}
            <Button
              variant="ghost"
              leftIcon={<Eye className="w-4 h-4" />}
              onClick={() => navigate(`/campaign/${campaignId}/characters`)}
              className="flex-1 justify-center"
            >
              Ver Personagens
            </Button>
            <Button
              variant="ghost"
              leftIcon={<Plus className="w-4 h-4" />}
              onClick={() => setShowCreateModal(true)}
              className="flex-1 justify-center"
            >
              Criar Personagem
            </Button>
          </div>
        </div>
      ) : null}

      {campaignId && (
        <CharacterCreationModal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          campaignId={campaignId}
          onCreate={(newChar) => {
            setCharacters((prev) => [...prev, newChar])
            setShowCreateModal(false)
          }}
        />
      )}
    </AppLayout>
  )
}
