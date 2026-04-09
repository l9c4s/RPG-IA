import React, { useState, useTransition } from 'react'
import { Sword, Shield, User, ChevronRight, ChevronLeft, Check, Sparkles } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { Modal } from './ui/Modal'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import type { Character } from '../types'
import { RACES, CLASSES, ALIGNMENTS, STANDARD_ARRAY } from '../lib/constants'
import { formatModifier } from '../lib/utils'

// ─── Step types ────────────────────────────────────────────────────────────
interface BasicInfo {
  name:            string
  race:            string
  character_class: string
  background:      string
  alignment:       string
}

interface AbilityScoreValues {
  strength:     number
  dexterity:    number
  constitution: number
  intelligence: number
  wisdom:       number
  charisma:     number
}

interface PersonalityInfo {
  personality_traits: string
  ideals:             string
  bonds:              string
  flaws:              string
}

type WizardStep = 1 | 2 | 3
type WizardMode = 'select' | 'ai' | 'manual'

interface AiGeneratedCharacter {
  name:            string
  race:            string
  character_class: string
  alignment:       string
  background:      string
  appearance:      string
  backstory:       string
  pixel_art_prompt: string
}

// ─── Step indicators ───────────────────────────────────────────────────────
const STEPS = [
  { step: 1, label: 'Identity',    icon: User   },
  { step: 2, label: 'Attributes',  icon: Shield },
  { step: 3, label: 'Personality', icon: Sword  },
] as const

function StepIndicator({ current }: { current: WizardStep }): React.ReactElement {
  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      {STEPS.map(({ step, label, icon: Icon }) => (
        <React.Fragment key={step}>
          <div className={`flex flex-col items-center gap-1 ${current === step ? 'opacity-100' : current > step ? 'opacity-60' : 'opacity-30'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all ${
              current > step
                ? 'bg-amber-600/30 border-amber-600/60'
                : current === step
                ? 'bg-amber-600/20 border-amber-500'
                : 'border-slate-600 bg-slate-800'
            }`}>
              {current > step ? (
                <Check className="w-4 h-4 text-amber-400" />
              ) : (
                <Icon className={`w-4 h-4 ${current === step ? 'text-amber-400' : 'text-slate-500'}`} />
              )}
            </div>
            <span className={`text-xs font-serif ${current === step ? 'text-amber-400' : 'text-slate-500'}`}>
              {label}
            </span>
          </div>
          {step < 3 && (
            <div className={`h-px flex-1 max-w-8 ${current > step ? 'bg-amber-600/50' : 'bg-slate-700'}`} />
          )}
        </React.Fragment>
      ))}
    </div>
  )
}

// ─── Step 1: Basic Info ────────────────────────────────────────────────────
interface Step1Props {
  data:     BasicInfo
  onChange: (data: BasicInfo) => void
  onNext:   () => void
}

function Step1({ data, onChange, onNext }: Step1Props): React.ReactElement {
  const [error, setError] = useState<string | null>(null)

  function handleNext(): void {
    if (!data.name.trim()) { setError('O nome do personagem é obrigatório.'); return }
    if (data.name.trim().length < 2) { setError('O nome deve ter pelo menos 2 caracteres.'); return }
    if (!data.character_class) { setError('Selecione uma classe para o personagem.'); return }
    setError(null)
    onNext()
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="text-red-300 text-sm bg-red-900/30 border border-red-700/40 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <Input
        label="Character Name"
        type="text"
        value={data.name}
        onChange={(e) => onChange({ ...data, name: e.target.value })}
        placeholder="Aragorn Elessar"
        autoFocus
        maxLength={60}
      />

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label-rune">Race</label>
          <select
            value={data.race}
            onChange={(e) => onChange({ ...data, race: e.target.value })}
            className="input-dark"
          >
            {RACES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>

        <div>
          <label className="label-rune">Class</label>
          <select
            value={data.character_class}
            onChange={(e) => onChange({ ...data, character_class: e.target.value })}
            className="input-dark"
          >
            {CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label-rune">Alignment</label>
          <select
            value={data.alignment}
            onChange={(e) => onChange({ ...data, alignment: e.target.value })}
            className="input-dark"
          >
            {ALIGNMENTS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <Input
          label="Background"
          type="text"
          value={data.background}
          onChange={(e) => onChange({ ...data, background: e.target.value })}
          placeholder="Acolyte, Soldier…"
          maxLength={60}
        />
      </div>

      <div className="flex justify-end pt-2">
        <Button
          variant="primary"
          rightIcon={<ChevronRight className="w-4 h-4" />}
          onClick={handleNext}
        >
          Next: Attributes
        </Button>
      </div>
    </div>
  )
}

// ─── Step 2: Ability Scores ────────────────────────────────────────────────
const ABILITY_FIELDS: { key: keyof AbilityScoreValues; label: string; short: string }[] = [
  { key: 'strength',     label: 'Strength',     short: 'STR' },
  { key: 'dexterity',    label: 'Dexterity',    short: 'DEX' },
  { key: 'constitution', label: 'Constitution', short: 'CON' },
  { key: 'intelligence', label: 'Intelligence', short: 'INT' },
  { key: 'wisdom',       label: 'Wisdom',       short: 'WIS' },
  { key: 'charisma',     label: 'Charisma',     short: 'CHA' },
]

interface Step2Props {
  data:     AbilityScoreValues
  onChange: (data: AbilityScoreValues) => void
  onNext:   () => void
  onBack:   () => void
}

function Step2({ data, onChange, onNext, onBack }: Step2Props): React.ReactElement {
  function applyStandardArray(): void {
    const [str, dex, con, int_, wis, cha] = STANDARD_ARRAY
    onChange({ strength: str, dexterity: dex, constitution: con, intelligence: int_, wisdom: wis, charisma: cha })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-slate-400 text-xs font-serif italic">
          Standard Array: 15, 14, 13, 12, 10, 8
        </p>
        <Button variant="ghost" size="sm" onClick={applyStandardArray}>
          Apply Standard Array
        </Button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {ABILITY_FIELDS.map(({ key, label, short }) => {
          const score = data[key]
          return (
            <div key={key} className="stat-box p-3">
              <label className="text-amber-500 text-xs font-serif font-semibold tracking-widest block mb-1">
                {short}
              </label>
              <input
                type="number"
                value={score}
                onChange={(e) => onChange({ ...data, [key]: Math.max(1, Math.min(20, Number(e.target.value))) })}
                min={1}
                max={20}
                className="w-full bg-transparent text-slate-100 text-xl font-bold text-center border-b border-amber-700/60 outline-none [appearance:textfield] mb-1"
              />
              <p className="text-slate-400 text-sm font-serif text-center">{formatModifier(score)}</p>
              <p className="text-slate-600 text-xs text-center">{label}</p>
            </div>
          )
        })}
      </div>

      <div className="flex justify-between pt-2">
        <Button variant="ghost" leftIcon={<ChevronLeft className="w-4 h-4" />} onClick={onBack}>
          Back
        </Button>
        <Button variant="primary" rightIcon={<ChevronRight className="w-4 h-4" />} onClick={onNext}>
          Next: Personality
        </Button>
      </div>
    </div>
  )
}

// ─── Step 3: Personality ───────────────────────────────────────────────────
interface Step3Props {
  data:      PersonalityInfo
  onChange:  (data: PersonalityInfo) => void
  onBack:    () => void
  onSubmit:  () => void
  isLoading: boolean
}

function Step3({ data, onChange, onBack, onSubmit, isLoading }: Step3Props): React.ReactElement {
  const fields: { key: keyof PersonalityInfo; label: string; placeholder: string }[] = [
    { key: 'personality_traits', label: 'Personality Traits', placeholder: 'I idolize a particular hero of my faith…' },
    { key: 'ideals',             label: 'Ideals',             placeholder: 'Charity. I always help those in need…' },
    { key: 'bonds',              label: 'Bonds',              placeholder: 'I would die to recover an ancient relic…' },
    { key: 'flaws',              label: 'Flaws',              placeholder: 'I am inflexible in my thinking…' },
  ]

  return (
    <div className="space-y-4">
      {fields.map(({ key, label, placeholder }) => (
        <div key={key}>
          <label className="label-rune">{label}</label>
          <textarea
            value={data[key]}
            onChange={(e) => onChange({ ...data, [key]: e.target.value })}
            placeholder={placeholder}
            className="input-dark resize-none h-16 text-sm"
            maxLength={300}
          />
        </div>
      ))}

      <div className="flex justify-between pt-2">
        <Button
          variant="ghost"
          leftIcon={<ChevronLeft className="w-4 h-4" />}
          onClick={onBack}
          disabled={isLoading}
        >
          Back
        </Button>
        <Button
          variant="primary"
          isLoading={isLoading}
          leftIcon={<Sword className="w-4 h-4" />}
          onClick={onSubmit}
        >
          {isLoading ? 'Creating…' : 'Create Character'}
        </Button>
      </div>
    </div>
  )
}

// ─── AI Generation panel ──────────────────────────────────────────────────
interface AiPanelProps {
  campaignId:   string
  onGenerated:  (basic: BasicInfo, persona: PersonalityInfo) => void
  onBack:       () => void
}

function AiPanel({ campaignId, onGenerated, onBack }: AiPanelProps): React.ReactElement {
  const [description,   setDescription]   = useState('')
  const [isGenerating,  setIsGenerating]  = useState(false)
  const [error,         setError]         = useState<string | null>(null)
  const [,              startTransition]  = useTransition()

  async function handleGenerate(): Promise<void> {
    if (!description.trim()) { setError('Descreva como deve ser o personagem.'); return }
    setIsGenerating(true)
    setError(null)
    try {
      const result = await api.post<AiGeneratedCharacter>(
        `/campaigns/${campaignId}/generate-character-8bit`,
        { description: description.trim() },
      )
      startTransition(() => {
        onGenerated(
          {
            name:            result.name,
            race:            result.race,
            character_class: result.character_class,
            background:      result.background,
            alignment:       result.alignment,
          },
          {
            personality_traits: result.appearance,
            ideals:             '',
            bonds:              result.backstory,
            flaws:              '',
          },
        )
      })
    } catch {
      setError('Falha ao gerar personagem. Tente novamente.')
      setIsGenerating(false)
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-slate-400 text-sm font-serif italic">
        Descreva o personagem em linguagem natural. A IA criará o conceito completo e pré-preencherá o formulário.
      </p>

      {error && (
        <div className="text-red-300 text-sm bg-red-900/30 border border-red-700/40 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <div>
        <label className="label-rune">Descrição do personagem</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Um elfo renegado que fugiu de sua cidade natal depois de roubar um artefato proibido…"
          className="input-dark resize-none h-28 text-sm"
          maxLength={500}
          autoFocus
          disabled={isGenerating}
        />
        <p className="text-slate-600 text-xs mt-1 text-right">{description.length}/500</p>
      </div>

      <div className="flex gap-3 pt-1">
        <Button
          variant="ghost"
          leftIcon={<ChevronLeft className="w-4 h-4" />}
          onClick={onBack}
          disabled={isGenerating}
          className="flex-1 justify-center"
        >
          Voltar
        </Button>
        <Button
          variant="primary"
          leftIcon={isGenerating ? undefined : <Sparkles className="w-4 h-4" />}
          isLoading={isGenerating}
          onClick={() => void handleGenerate()}
          className="flex-1 justify-center"
        >
          {isGenerating ? 'Gerando…' : 'Gerar Personagem'}
        </Button>
      </div>
    </div>
  )
}

// ─── Main Modal ────────────────────────────────────────────────────────────
interface CharacterCreationModalProps {
  isOpen:          boolean
  onClose:         () => void
  campaignId:      string
  onCreate:        (character: Character) => void
  onImagePending?: (characterId: string, imageId: string) => void
}

const DEFAULT_BASIC: BasicInfo = {
  name:            '',
  race:            'Humano',
  character_class: 'Guerreiro',
  background:      'Soldier',
  alignment:       'Leal e Bom',
}

const DEFAULT_ABILITY: AbilityScoreValues = {
  strength: 10, dexterity: 10, constitution: 10,
  intelligence: 10, wisdom: 10, charisma: 10,
}

const DEFAULT_PERSONALITY: PersonalityInfo = {
  personality_traits: '', ideals: '', bonds: '', flaws: '',
}

export default function CharacterCreationModal({
  isOpen,
  onClose,
  campaignId,
  onCreate,
  onImagePending,
}: CharacterCreationModalProps): React.ReactElement {
  const { user }                       = useAuth()
  const [mode,         setMode]         = useState<WizardMode>('select')
  const [step,         setStep]         = useState<WizardStep>(1)
  const [isLoading,    setIsLoading]    = useState(false)
  const [error,        setError]        = useState<string | null>(null)
  const [basicInfo,    setBasicInfo]    = useState<BasicInfo>(DEFAULT_BASIC)
  const [abilityScores, setAbilityScores] = useState<AbilityScoreValues>(DEFAULT_ABILITY)
  const [personality,  setPersonality]  = useState<PersonalityInfo>(DEFAULT_PERSONALITY)

  // Reset internal state whenever the modal is opened
  const prevOpenRef = React.useRef(false)
  React.useEffect(() => {
    if (isOpen && !prevOpenRef.current) reset()
    prevOpenRef.current = isOpen
  }, [isOpen])

  function reset(): void {
    setMode('select')
    setStep(1)
    setError(null)
    setBasicInfo(DEFAULT_BASIC)
    setAbilityScores(DEFAULT_ABILITY)
    setPersonality(DEFAULT_PERSONALITY)
  }

  function handleClose(): void {
    if (isLoading) return
    reset()
    onClose()
  }

  function handleAiGenerated(basic: BasicInfo, persona: PersonalityInfo): void {
    setBasicInfo(basic)
    setPersonality(persona)
    setMode('manual')
    setStep(1)
  }

  async function handleCreate(): Promise<void> {
    setIsLoading(true)
    setError(null)
    try {
      // Build backstory by combining personality fields the model doesn't have separately
      const backstoryParts = [
        personality.bonds && `Bonds: ${personality.bonds}`,
        personality.ideals && `Ideals: ${personality.ideals}`,
        personality.flaws && `Flaws: ${personality.flaws}`,
      ].filter(Boolean)

      if (!basicInfo.character_class) {
        setError('Selecione uma classe para o personagem antes de continuar.')
        setIsLoading(false)
        return
      }

      const payload = {
        campaign_id: campaignId,
        owner_id:    user?.id,
        name:        basicInfo.name.trim(),
        race:        basicInfo.race,
        class:       basicInfo.character_class,   // Pydantic alias
        background:  basicInfo.background || undefined,
        alignment:   basicInfo.alignment || undefined,
        level:       1,
        appearance:  personality.personality_traits || undefined,
        backstory:   backstoryParts.length ? backstoryParts.join('\n') : undefined,
        attributes:  abilityScores,
      }
      const character = await api.post<Character>('/characters', payload)
      onCreate(character)
      reset()
      onClose()

      // Dispara geração de imagem e captura image_id para SSE
      const appearance = payload.appearance || ''
      const imageDescription = [
        appearance,
        `${payload.race} ${payload.class}`,
        payload.alignment,
      ].filter(Boolean).join(', ')
      const characterId = character.id
      api.post<{ image_id: string }>('/generate/character', {
        description:   imageDescription,
        character_id:  characterId,
        campaign_id:   campaignId,
        style:         'pixel_art',
      }).then((resp) => {
        if (resp.image_id && onImagePending) onImagePending(characterId, resp.image_id)
      }).catch(() => { /* ignora falha silenciosamente */ })
    } catch {
      setError('Failed to create character. Please try again.')
      setIsLoading(false)
    }
  }

  const modalTitle =
    mode === 'select' ? 'Criar Personagem' :
    mode === 'ai'     ? 'Gerar com IA' :
    step === 1        ? 'Personagem — Identidade' :
    step === 2        ? 'Personagem — Atributos' :
                        'Personagem — Personalidade'

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={modalTitle} size="md">

      {/* Mode selector */}
      {mode === 'select' && (
        <div className="space-y-3 py-2">
          <p className="text-slate-400 text-sm font-serif italic text-center mb-4">
            Como deseja criar seu personagem?
          </p>
          <button
            onClick={() => setMode('manual')}
            className="w-full flex items-center gap-4 p-4 rounded-lg border border-slate-700 bg-slate-800/50 hover:border-amber-600/60 hover:bg-slate-800 transition-all text-left group"
          >
            <div className="w-10 h-10 rounded-full bg-amber-600/20 border border-amber-600/40 flex items-center justify-center shrink-0">
              <User className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="font-serif text-amber-300 group-hover:text-amber-200 transition-colors">Criar Manualmente</p>
              <p className="text-slate-500 text-xs mt-0.5">Preencha raça, classe e atributos você mesmo</p>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-600 ml-auto" />
          </button>

          <button
            onClick={() => setMode('ai')}
            className="w-full flex items-center gap-4 p-4 rounded-lg border border-slate-700 bg-slate-800/50 hover:border-amber-600/60 hover:bg-slate-800 transition-all text-left group"
          >
            <div className="w-10 h-10 rounded-full bg-amber-600/20 border border-amber-600/40 flex items-center justify-center shrink-0">
              <Sparkles className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="font-serif text-amber-300 group-hover:text-amber-200 transition-colors">Gerar com IA</p>
              <p className="text-slate-500 text-xs mt-0.5">Descreva o personagem e a IA pré-preenche o formulário</p>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-600 ml-auto" />
          </button>
        </div>
      )}

      {/* AI generation panel */}
      {mode === 'ai' && (
        <AiPanel
          campaignId={campaignId}
          onGenerated={handleAiGenerated}
          onBack={() => setMode('select')}
        />
      )}

      {/* Manual wizard */}
      {mode === 'manual' && (
        <>
          <StepIndicator current={step} />

          {error && (
            <div className="mb-4 text-red-300 text-sm bg-red-900/30 border border-red-700/40 rounded-md px-3 py-2">
              {error}
            </div>
          )}

          {step === 1 && (
            <Step1 data={basicInfo} onChange={setBasicInfo} onNext={() => setStep(2)} />
          )}
          {step === 2 && (
            <Step2
              data={abilityScores}
              onChange={setAbilityScores}
              onNext={() => setStep(3)}
              onBack={() => setStep(1)}
            />
          )}
          {step === 3 && (
            <Step3
              data={personality}
              onChange={setPersonality}
              onBack={() => setStep(2)}
              onSubmit={handleCreate}
              isLoading={isLoading}
            />
          )}
        </>
      )}
    </Modal>
  )
}
