import React, { useState, useEffect, useCallback, lazy, Suspense } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Users, Map, Sword, Plus, Bot, AlertCircle, ChevronLeft,
  Check, Loader2, RefreshCw,
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { AppLayout } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import type { Campaign, Character, Location } from '../types'

const CharacterCreationModal = lazy(() => import('../components/CharacterCreationModal'))
const WorldMap = lazy(() => import('../components/WorldMap'))

// ── Step indicator ─────────────────────────────────────────────────────────
type SetupStep = 1 | 2 | 3

const STEPS = [
  { step: 1 as SetupStep, label: 'Personagens', icon: Users  },
  { step: 2 as SetupStep, label: 'Mapa',        icon: Map    },
  { step: 3 as SetupStep, label: 'Jogar',       icon: Sword  },
] as const

function StepIndicator({ current }: { current: SetupStep }): React.ReactElement {
  return (
    <div className="flex items-center justify-center gap-3 mb-8">
      {STEPS.map(({ step, label, icon: Icon }) => (
        <React.Fragment key={step}>
          <div className={`flex flex-col items-center gap-1.5 ${current === step ? 'opacity-100' : current > step ? 'opacity-70' : 'opacity-30'}`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all ${
              current > step
                ? 'bg-amber-600/30 border-amber-600/60'
                : current === step
                ? 'bg-amber-600/20 border-amber-500'
                : 'border-slate-600 bg-slate-800'
            }`}>
              {current > step
                ? <Check className="w-5 h-5 text-amber-400" />
                : <Icon className={`w-5 h-5 ${current === step ? 'text-amber-400' : 'text-slate-500'}`} />
              }
            </div>
            <span className={`text-xs font-serif ${current === step ? 'text-amber-400' : 'text-slate-500'}`}>
              {label}
            </span>
          </div>
          {step < 3 && (
            <div className={`h-px w-12 mt-[-10px] ${current > step ? 'bg-amber-600/50' : 'bg-slate-700'}`} />
          )}
        </React.Fragment>
      ))}
    </div>
  )
}

// ── Step 1: Personagens ────────────────────────────────────────────────────
interface Step1Props {
  campaignId: string
  characters: Character[]
  onCharacterAdded: (char: Character) => void
  onAiAdded: (char: Character) => void
  onNext: () => void
}

function StepPersonagens({ campaignId, characters, onCharacterAdded, onAiAdded, onNext }: Step1Props): React.ReactElement {
  const { user } = useAuth()
  const [showCreate, setShowCreate] = useState(false)
  const [addingAi,   setAddingAi]   = useState(false)
  const [aiError,    setAiError]    = useState<string | null>(null)

  async function handleAddAi(): Promise<void> {
    setAddingAi(true)
    setAiError(null)
    try {
      const char = await api.post<Character>(`/campaigns/${campaignId}/ai-player`, {})
      onAiAdded(char)
    } catch {
      setAiError('Falha ao adicionar companheiro IA.')
    } finally {
      setAddingAi(false)
    }
  }

  const myChar = characters.find((c) => c.player_id === user?.id)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-serif text-amber-400 mb-1">Personagens da Campanha</h2>
        <p className="text-slate-400 text-sm font-serif italic">
          Crie pelo menos 1 personagem para continuar. Você pode adicionar companheiros de IA também.
        </p>
      </div>

      {/* Character list */}
      <div className="space-y-3">
        {characters.length === 0 && (
          <p className="text-slate-500 font-serif italic text-sm text-center py-6 border border-dashed border-slate-700 rounded-lg">
            Nenhum personagem ainda. Crie o seu!
          </p>
        )}
        {characters.map((char) => (
          <div
            key={char.id}
            className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg border border-slate-700/40"
          >
            <div>
              <p className="text-slate-200 font-semibold text-sm">{char.name}</p>
              <p className="text-slate-500 text-xs">Nível {char.level} {char.character_class} · {char.race}</p>
            </div>
            <div className="flex items-center gap-2">
              {char.player_id === user?.id && <Badge variant="success">Você</Badge>}
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      {aiError && (
        <div className="flex items-center gap-2 text-red-300 text-sm bg-red-900/30 border border-red-700/40 rounded-md px-3 py-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {aiError}
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-3">
        {!myChar && (
          <Button
            variant="primary"
            leftIcon={<Plus className="w-4 h-4" />}
            onClick={() => setShowCreate(true)}
            className="flex-1 justify-center"
          >
            Criar Personagem
          </Button>
        )}
        <Button
          variant="ghost"
          leftIcon={addingAi ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bot className="w-4 h-4" />}
          onClick={handleAddAi}
          disabled={addingAi}
          className="flex-1 justify-center"
        >
          {addingAi ? 'Adicionando…' : 'Adicionar Companheiro IA'}
        </Button>
      </div>

      <div className="flex justify-end pt-2">
        <Button
          variant="primary"
          rightIcon={<Map className="w-4 h-4" />}
          onClick={onNext}
          disabled={characters.length < 1}
        >
          Próximo: Gerar Mapa
        </Button>
      </div>

      <Suspense fallback={null}>
        <CharacterCreationModal
          isOpen={showCreate}
          onClose={() => setShowCreate(false)}
          campaignId={campaignId}
          onCreate={(char) => {
            onCharacterAdded(char)
            setShowCreate(false)
          }}
        />
      </Suspense>
    </div>
  )
}

// ── Step 2: Mapa ───────────────────────────────────────────────────────────
interface Step2Props {
  campaignId: string
  locations: Location[]
  onMapGenerated: (locs: Location[]) => void
  onNext: () => void
  onBack: () => void
}

function StepMapa({ campaignId, locations, onMapGenerated, onNext, onBack }: Step2Props): React.ReactElement {
  const [isGenerating, setIsGenerating] = useState(false)
  const [error,        setError]        = useState<string | null>(null)

  async function handleGenerate(): Promise<void> {
    setIsGenerating(true)
    setError(null)
    try {
      const result = await api.post<{ locations: Location[] }>(`/campaigns/${campaignId}/generate-map`, {})
      onMapGenerated(result.locations)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Falha ao gerar o mapa. Tente novamente.')
    } finally {
      setIsGenerating(false)
    }
  }

  const mapGenerated = locations.length > 0

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-serif text-amber-400 mb-1">Mapa do Mundo</h2>
        <p className="text-slate-400 text-sm font-serif italic">
          {mapGenerated
            ? 'Mapa gerado! Clique nos locais para explorar.'
            : 'O GM irá gerar os locais do mundo com base nos dados da campanha.'}
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-300 text-sm bg-red-900/30 border border-red-700/40 rounded-md px-3 py-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {!mapGenerated ? (
        <div className="flex flex-col items-center gap-4 py-12 border border-dashed border-slate-700 rounded-lg">
          <Map className="w-16 h-16 text-amber-700/40" />
          <p className="text-slate-500 font-serif italic text-sm text-center max-w-xs">
            O mapa será criado usando IA com base no título, sistema e descrição da sua campanha.
          </p>
          <Button
            variant="primary"
            leftIcon={isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Map className="w-4 h-4" />}
            onClick={handleGenerate}
            isLoading={isGenerating}
          >
            {isGenerating ? 'Gerando mapa…' : 'Gerar Mapa com IA'}
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <Suspense fallback={<div className="h-64 flex items-center justify-center"><Spinner size="lg" /></div>}>
            <WorldMap
              campaignId={campaignId}
              onLocationSelect={() => undefined}
            />
          </Suspense>
          <div className="flex justify-end">
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              onClick={handleGenerate}
              disabled={isGenerating}
            >
              {isGenerating ? 'Gerando…' : 'Regenerar'}
            </Button>
          </div>
        </div>
      )}

      <div className="flex justify-between pt-2">
        <Button
          variant="ghost"
          leftIcon={<ChevronLeft className="w-4 h-4" />}
          onClick={onBack}
          disabled={isGenerating}
        >
          Voltar
        </Button>
        <Button
          variant="primary"
          rightIcon={<Sword className="w-4 h-4" />}
          onClick={onNext}
          disabled={!mapGenerated}
        >
          Próximo: Jogar
        </Button>
      </div>
    </div>
  )
}

// ── Step 3: Jogar ──────────────────────────────────────────────────────────
interface Step3Props {
  campaign: Campaign
  characters: Character[]
  onPlay: () => void
  onBack: () => void
}

function StepJogar({ campaign, characters, onPlay, onBack }: Step3Props): React.ReactElement {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-serif text-amber-400 mb-1">Pronto para jogar!</h2>
        <p className="text-slate-400 text-sm font-serif italic">
          Revise o resumo da campanha e entre na sessão.
        </p>
      </div>

      <div className="card-rune p-5 space-y-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-slate-500 font-serif mb-1">Campanha</p>
          <p className="text-amber-400 font-serif text-lg">{campaign.title}</p>
          <p className="text-slate-500 text-xs">{campaign.rpg_system}</p>
        </div>

        {campaign.description && (
          <p className="text-slate-300 text-sm italic leading-relaxed border-t border-slate-700/50 pt-3">
            {campaign.description}
          </p>
        )}

        <div className="border-t border-slate-700/50 pt-3">
          <p className="text-xs uppercase tracking-widest text-slate-500 font-serif mb-2">Grupo ({characters.length})</p>
          <div className="space-y-1.5">
            {characters.map((char) => (
              <div key={char.id} className="flex items-center gap-2 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-600" />
                <span className="text-slate-300">{char.name}</span>
                <span className="text-slate-500 text-xs">· {char.character_class} {char.race}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 pt-2">
        <Button
          variant="ghost"
          leftIcon={<ChevronLeft className="w-4 h-4" />}
          onClick={onBack}
        >
          Voltar
        </Button>
        <Button
          variant="primary"
          leftIcon={<Sword className="w-4 h-4" />}
          onClick={onPlay}
          className="flex-1 justify-center"
        >
          Entrar na Sessão
        </Button>
      </div>
    </div>
  )
}

// ── Main Lobby ─────────────────────────────────────────────────────────────
export default function Lobby(): React.ReactElement {
  const { id: campaignId }            = useParams<{ id: string }>()
  const navigate                      = useNavigate()

  const [campaign,    setCampaign]    = useState<Campaign | null>(null)
  const [characters,  setCharacters]  = useState<Character[]>([])
  const [locations,   setLocations]   = useState<Location[]>([])
  const [step,        setStep]        = useState<SetupStep>(1)
  const [isLoading,   setIsLoading]   = useState(true)
  const [error,       setError]       = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (!campaignId) return
    setIsLoading(true)
    setError(null)
    try {
      const [campaignData, charData, locData] = await Promise.all([
        api.get<Campaign>(`/campaigns/${campaignId}`),
        api.get<Character[]>(`/campaigns/${campaignId}/characters`),
        api.get<Location[]>(`/campaigns/${campaignId}/locations`).catch(() => [] as Location[]),
      ])
      setCampaign(campaignData)
      setCharacters(charData)
      setLocations(locData)

      // Restore wizard step based on campaign state
      if (campaignData.status === 'active' && locData.length > 0) {
        setStep(3)
      } else if (charData.length > 0) {
        setStep(2)
      } else {
        setStep(1)
      }
    } catch {
      setError('Falha ao carregar dados da campanha.')
    } finally {
      setIsLoading(false)
    }
  }, [campaignId])

  useEffect(() => { void fetchData() }, [fetchData])

  if (!campaignId) return <></>

  return (
    <AppLayout>
      <div className="max-w-2xl mx-auto">
        {/* Back */}
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
            <p className="text-slate-400 font-serif italic text-sm">Preparando a aventura…</p>
          </div>
        ) : error ? (
          <div className="flex items-center gap-2 bg-red-900/40 border border-red-700/60 rounded-lg px-5 py-4 text-red-300 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
            <button onClick={fetchData} className="ml-auto text-xs underline">Tentar novamente</button>
          </div>
        ) : campaign ? (
          <>
            {/* Campaign header */}
            <div className="mb-6">
              <h1 className="text-2xl font-serif text-amber-400">{campaign.title}</h1>
              <p className="text-slate-500 text-sm font-serif">{campaign.rpg_system}</p>
            </div>

            <StepIndicator current={step} />

            <div className="card-rune p-6">
              {step === 1 && (
                <StepPersonagens
                  campaignId={campaignId}
                  characters={characters}
                  onCharacterAdded={(char) => setCharacters((prev) => [...prev, char])}
                  onAiAdded={(char) => setCharacters((prev) => [...prev, char])}
                  onNext={() => setStep(2)}
                />
              )}

              {step === 2 && (
                <StepMapa
                  campaignId={campaignId}
                  locations={locations}
                  onMapGenerated={(locs) => setLocations(locs)}
                  onNext={() => setStep(3)}
                  onBack={() => setStep(1)}
                />
              )}

              {step === 3 && (
                <StepJogar
                  campaign={campaign}
                  characters={characters}
                  onPlay={() => navigate(`/campaign/${campaignId}`)}
                  onBack={() => setStep(2)}
                />
              )}
            </div>
          </>
        ) : null}
      </div>
    </AppLayout>
  )
}
