import React, { useState } from 'react'
import { Sword, Shield, User, ChevronRight, ChevronLeft, Check } from 'lucide-react'
import { api } from '../api/client'
import { Modal } from './ui/Modal'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Spinner } from './ui/Spinner'
import type { Character } from '../types'
import { RACES, CLASSES, ALIGNMENTS, STANDARD_ARRAY } from '../lib/constants'
import { dndModifier, formatModifier } from '../lib/utils'

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
    if (!data.name.trim()) { setError('Character name is required.'); return }
    if (data.name.trim().length < 2) { setError('Name must be at least 2 characters.'); return }
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
          const mod   = dndModifier(score)
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

// ─── Main Modal ────────────────────────────────────────────────────────────
interface CharacterCreationModalProps {
  isOpen:     boolean
  onClose:    () => void
  campaignId: string
  onCreate:   (character: Character) => void
}

export default function CharacterCreationModal({
  isOpen,
  onClose,
  campaignId,
  onCreate,
}: CharacterCreationModalProps): React.ReactElement {
  const [step,      setStep]      = useState<WizardStep>(1)
  const [isLoading, setIsLoading] = useState(false)
  const [error,     setError]     = useState<string | null>(null)

  const [basicInfo, setBasicInfo] = useState<BasicInfo>({
    name:            '',
    race:            'Humano',
    character_class: 'Guerreiro',
    background:      'Soldier',
    alignment:       'Leal e Bom',
  })

  const [abilityScores, setAbilityScores] = useState<AbilityScoreValues>({
    strength:     10,
    dexterity:    10,
    constitution: 10,
    intelligence: 10,
    wisdom:       10,
    charisma:     10,
  })

  const [personality, setPersonality] = useState<PersonalityInfo>({
    personality_traits: '',
    ideals:             '',
    bonds:              '',
    flaws:              '',
  })

  async function handleCreate(): Promise<void> {
    setIsLoading(true)
    setError(null)
    try {
      const payload = {
        campaign_id:      Number(campaignId),
        name:             basicInfo.name,
        race:             basicInfo.race,
        character_class:  basicInfo.character_class,
        background:       basicInfo.background,
        alignment:        basicInfo.alignment,
        level:            1,
        experience:       0,
        ability_scores:   abilityScores,
        personality_traits: personality.personality_traits,
        ideals:           personality.ideals,
        bonds:            personality.bonds,
        flaws:            personality.flaws,
      }
      const character = await api.post<Character>('/characters', payload)
      onCreate(character)
      onClose()
    } catch {
      setError('Failed to create character. Please try again.')
      setIsLoading(false)
    }
  }

  function handleClose(): void {
    if (isLoading) return
    setStep(1)
    setError(null)
    onClose()
  }

  const STEP_TITLES: Record<WizardStep, string> = {
    1: 'Create Character — Identity',
    2: 'Create Character — Attributes',
    3: 'Create Character — Personality',
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={STEP_TITLES[step]}
      size="md"
    >
      <StepIndicator current={step} />

      {error && (
        <div className="mb-4 text-red-300 text-sm bg-red-900/30 border border-red-700/40 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {step === 1 && (
        <Step1
          data={basicInfo}
          onChange={setBasicInfo}
          onNext={() => setStep(2)}
        />
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
    </Modal>
  )
}
