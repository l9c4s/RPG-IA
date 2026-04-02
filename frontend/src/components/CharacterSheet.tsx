import React, { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ChevronLeft, Edit3, Save, X, Plus, Trash2,
  Heart, Shield, Zap, Star, Users, AlertCircle
} from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { Spinner } from './ui/Spinner'
import type {
  Character, CharacterStatus, CharacterAttributes,
  InventoryItem, CharacterAbility
} from '../types'

// ─── Helpers ──────────────────────────────────────────────────────────────
function abilityModifier(score: number): number {
  return Math.floor((score - 10) / 2)
}

function formatModifier(mod: number): string {
  return mod >= 0 ? `+${mod}` : `${mod}`
}

type AbilityKey = 'strength' | 'dexterity' | 'constitution' | 'intelligence' | 'wisdom' | 'charisma'

const ABILITY_NAMES: AbilityKey[] = [
  'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
]

const ABILITY_SHORT: Record<AbilityKey, string> = {
  strength:     'STR',
  dexterity:    'DEX',
  constitution: 'CON',
  intelligence: 'INT',
  wisdom:       'WIS',
  charisma:     'CHA',
}

const DEFAULT_STATUS: CharacterStatus = {
  id: '', character_id: '', updated_at: '',
  hp_current: 0, hp_max: 0, hp_temp: 0,
  conditions: [], spell_slots: {}, exhaustion: 0,
  death_saves_success: 0, death_saves_failure: 0,
}

const DEFAULT_ATTRS: CharacterAttributes = {
  id: '', character_id: '',
  strength: 10, dexterity: 10, constitution: 10,
  intelligence: 10, wisdom: 10, charisma: 10,
  armor_class: 10, initiative: 0, speed: 30,
}

const CONDITIONS: string[] = [
  'Blinded', 'Charmed', 'Deafened', 'Exhaustion', 'Frightened',
  'Grappled', 'Incapacitated', 'Invisible', 'Paralyzed', 'Petrified',
  'Poisoned', 'Prone', 'Restrained', 'Stunned', 'Unconscious',
]

const SKILL_ABILITY: Record<string, AbilityKey> = {
  acrobatics:      'dexterity',
  animal_handling: 'wisdom',
  arcana:          'intelligence',
  athletics:       'strength',
  deception:       'charisma',
  history:         'intelligence',
  insight:         'wisdom',
  intimidation:    'charisma',
  investigation:   'intelligence',
  medicine:        'wisdom',
  nature:          'intelligence',
  perception:      'wisdom',
  performance:     'charisma',
  persuasion:      'charisma',
  religion:        'intelligence',
  sleight_of_hand: 'dexterity',
  stealth:         'dexterity',
  survival:        'wisdom',
}

function proficiencyBonus(level: number): number {
  return Math.ceil(level / 4) + 1
}

// ─── Stat Box ──────────────────────────────────────────────────────────────
interface StatBoxProps {
  name:  string
  score: number
  edit?: boolean
  onChange?: (v: number) => void
}

function StatBox({ name, score, edit = false, onChange }: StatBoxProps): React.ReactElement {
  const mod = abilityModifier(score)
  return (
    <div className="stat-box">
      <p className="text-amber-500 text-xs font-serif font-semibold tracking-widest">{name}</p>
      {edit && onChange ? (
        <input
          type="number"
          value={score}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-12 bg-transparent text-slate-100 text-xl font-bold text-center border-b border-amber-700/60 outline-none [appearance:textfield]"
          min={1} max={30}
        />
      ) : (
        <p className="text-slate-100 text-xl font-bold font-serif">{score}</p>
      )}
      <p className="text-slate-400 text-sm font-serif">{formatModifier(mod)}</p>
    </div>
  )
}

// ─── HP Tracker ────────────────────────────────────────────────────────────
interface HpTrackerProps {
  status:   CharacterStatus
  edit:     boolean
  onChange: (status: CharacterStatus) => void
}

function HpTracker({ status, edit, onChange }: HpTrackerProps): React.ReactElement {
  const pct      = Math.max(0, Math.min(100, (status.hp_current / status.hp_max) * 100))
  const hpColor  = pct > 50 ? 'bg-green-600' : pct > 25 ? 'bg-amber-500' : 'bg-red-600'

  return (
    <div className="card-rune p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Heart className="w-4 h-4 text-red-500" />
        <h3 className="font-serif text-amber-400 text-sm tracking-wide">Hit Points</h3>
      </div>

      <div className="hp-track">
        <div className={`h-full ${hpColor} transition-all duration-500 rounded-full`} style={{ width: `${pct}%` }} />
      </div>

      <div className="grid grid-cols-3 gap-2">
        {(['hp_current', 'hp_max', 'hp_temp'] as const).map((field) => (
          <div key={field} className="text-center">
            <label className="label-rune text-center">
              {field === 'hp_current' ? 'Current' : field === 'hp_max' ? 'Max' : 'Temp'}
            </label>
            {edit ? (
              <input
                type="number"
                value={status[field]}
                onChange={(e) => onChange({ ...status, [field]: Number(e.target.value) })}
                className="w-full input-dark text-center text-lg font-bold [appearance:textfield]"
                min={field === 'hp_current' ? -99 : 0}
                max={field === 'hp_max' ? 999 : 99}
              />
            ) : (
              <p className={`text-xl font-bold font-serif ${
                field === 'hp_temp' && status.hp_temp > 0 ? 'text-blue-400' : 'text-slate-100'
              }`}>
                {status[field]}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Death saves */}
      {status.hp_current <= 0 && (
        <div className="pt-2 border-t border-slate-700/40">
          <p className="label-rune text-center mb-2">Death Saves</p>
          <div className="flex justify-around">
            <div className="text-center">
              <p className="text-xs text-green-400 mb-1">Successes</p>
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <div key={i} className={`w-4 h-4 rounded-full border-2 ${i < status.death_saves_success ? 'bg-green-500 border-green-400' : 'border-slate-600'}`} />
                ))}
              </div>
            </div>
            <div className="text-center">
              <p className="text-xs text-red-400 mb-1">Failures</p>
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <div key={i} className={`w-4 h-4 rounded-full border-2 ${i < status.death_saves_failure ? 'bg-red-500 border-red-400' : 'border-slate-600'}`} />
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Conditions ────────────────────────────────────────────────────────────
interface ConditionsPanelProps {
  conditions: string[]
  edit:       boolean
  onChange:   (c: string[]) => void
}

function ConditionsPanel({ conditions, edit, onChange }: ConditionsPanelProps): React.ReactElement {
  const toggle = (c: string) => {
    if (conditions.includes(c)) onChange(conditions.filter((x) => x !== c))
    else onChange([...conditions, c])
  }

  return (
    <div className="card-rune p-4">
      <h3 className="font-serif text-amber-400 text-sm tracking-wide mb-3">Conditions</h3>
      <div className="flex flex-wrap gap-1.5">
        {CONDITIONS.map((c) => {
          const active = conditions.includes(c)
          return edit ? (
            <button
              key={c}
              onClick={() => toggle(c)}
              className={`badge text-xs cursor-pointer transition-all ${
                active ? 'badge-condition' : 'bg-slate-800 border border-slate-700 text-slate-500 hover:border-purple-700'
              }`}
            >
              {c}
            </button>
          ) : active ? (
            <span key={c} className="badge-condition">{c}</span>
          ) : null
        })}
        {!edit && conditions.length === 0 && (
          <p className="text-slate-500 text-xs font-serif italic">No conditions</p>
        )}
      </div>
    </div>
  )
}

// ─── Spell Slots ───────────────────────────────────────────────────────────
interface SpellSlotsPanelProps {
  slots:    Record<string, number>
  edit:     boolean
  onChange: (slots: Record<string, number>) => void
}

function SpellSlotsPanel({ slots, edit, onChange }: SpellSlotsPanelProps): React.ReactElement {
  const entries = Object.entries(slots).sort(([a], [b]) => Number(a) - Number(b))

  if (entries.length === 0) {
    return (
      <div className="card-rune p-4">
        <h3 className="font-serif text-amber-400 text-sm tracking-wide mb-2">Spell Slots</h3>
        <p className="text-slate-500 text-xs font-serif italic">No spell slots</p>
      </div>
    )
  }

  return (
    <div className="card-rune p-4">
      <h3 className="font-serif text-amber-400 text-sm tracking-wide mb-3">Spell Slots</h3>
      <div className="space-y-2">
        {entries.map(([level, remaining]) => (
          <div key={level} className="flex items-center gap-3">
            <span className="text-slate-400 text-xs w-14 font-serif">Level {level}</span>
            <span className="text-slate-100 text-sm font-bold">{remaining}</span>
            {edit && (
              <div className="flex gap-1">
                <button
                  onClick={() => onChange({ ...slots, [level]: Math.max(0, remaining - 1) })}
                  className="text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-red-400"
                >−</button>
                <button
                  onClick={() => onChange({ ...slots, [level]: remaining + 1 })}
                  className="text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-green-400"
                >+</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Inventory ─────────────────────────────────────────────────────────────
interface InventoryPanelProps {
  items:    InventoryItem[]
  edit:     boolean
  onChange: (items: InventoryItem[]) => void
}

function InventoryPanel({ items, edit, onChange }: InventoryPanelProps): React.ReactElement {
  function addItem(): void {
    const newItem: InventoryItem = {
      id:           crypto.randomUUID(),
      character_id: '',
      item_name:    'New Item',
      item_type:    'misc',
      quantity:     1,
      weight:       0,
      value_gp:     0,
      properties:   {},
      equipped:     false,
      created_at:   new Date().toISOString(),
    }
    onChange([...items, newItem])
  }

  function removeItem(id: string): void {
    onChange(items.filter((i) => i.id !== id))
  }

  function updateItem(id: string, patch: Partial<InventoryItem>): void {
    onChange(items.map((i) => (i.id === id ? { ...i, ...patch } : i)))
  }

  return (
    <div className="card-rune p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-serif text-amber-400 text-sm tracking-wide">Inventory</h3>
        {edit && (
          <button onClick={addItem} className="btn-ghost py-0.5 px-2 text-xs">
            <Plus className="w-3 h-3" /> Add
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="text-slate-500 text-xs font-serif italic">Empty pack</p>
      ) : (
        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
          {items.map((item) => (
            <div key={item.id} className={`flex items-center gap-2 p-2 rounded-md text-sm ${item.equipped ? 'bg-amber-900/20 border border-amber-700/30' : 'bg-slate-800/50'}`}>
              {edit ? (
                <>
                  <input
                    type="text"
                    value={item.item_name}
                    onChange={(e) => updateItem(item.id, { item_name: e.target.value })}
                    className="flex-1 bg-transparent text-slate-200 text-xs outline-none border-b border-transparent focus:border-amber-700"
                  />
                  <input
                    type="number"
                    value={item.quantity}
                    onChange={(e) => updateItem(item.id, { quantity: Number(e.target.value) })}
                    className="w-10 bg-slate-900 text-slate-300 text-xs text-center rounded border border-slate-700 [appearance:textfield] px-1 py-0.5"
                    min={0}
                  />
                  <button
                    onClick={() => updateItem(item.id, { equipped: !item.equipped })}
                    className={`text-xs px-1.5 py-0.5 rounded ${item.equipped ? 'bg-amber-700/40 text-amber-300' : 'text-slate-600 hover:text-amber-500'}`}
                  >
                    E
                  </button>
                  <button onClick={() => removeItem(item.id)} className="text-slate-600 hover:text-red-400">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-slate-200 text-xs truncate">{item.item_name}</span>
                  <span className="text-slate-500 text-xs">×{item.quantity}</span>
                  {item.equipped && <span className="badge badge-warning text-[10px]">E</span>}
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Abilities/Features ────────────────────────────────────────────────────
interface AbilitiesPanelProps {
  abilities: CharacterAbility[]
  edit:      boolean
  onChange:  (a: CharacterAbility[]) => void
}

function AbilitiesPanel({ abilities, edit, onChange }: AbilitiesPanelProps): React.ReactElement {
  function addAbility(): void {
    onChange([...abilities, {
      id: crypto.randomUUID(), character_id: '',
      ability_name: 'New Ability', ability_type: 'feature',
      description: null, spell_level: null, uses_max: null, uses_remaining: null, recharge: null,
    }])
  }

  return (
    <div className="card-rune p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-serif text-amber-400 text-sm tracking-wide">Abilities & Features</h3>
        {edit && (
          <button onClick={addAbility} className="btn-ghost py-0.5 px-2 text-xs">
            <Plus className="w-3 h-3" /> Add
          </button>
        )}
      </div>
      {abilities.length === 0 ? (
        <p className="text-slate-500 text-xs font-serif italic">No abilities listed</p>
      ) : (
        <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
          {abilities.map((ab, idx) => (
            <div key={ab.id} className="bg-slate-800/50 rounded-md p-2.5 text-sm">
              {edit ? (
                <div className="space-y-1">
                  <input
                    value={ab.ability_name}
                    onChange={(e) => {
                      const next = [...abilities]; next[idx] = { ...ab, ability_name: e.target.value }; onChange(next)
                    }}
                    className="w-full bg-transparent text-amber-400 text-xs font-semibold outline-none border-b border-amber-700/40"
                  />
                  <textarea
                    value={ab.description ?? ''}
                    onChange={(e) => {
                      const next = [...abilities]; next[idx] = { ...ab, description: e.target.value }; onChange(next)
                    }}
                    className="w-full bg-transparent text-slate-300 text-xs resize-none outline-none"
                    rows={2}
                  />
                  <div className="flex justify-end">
                    <button onClick={() => onChange(abilities.filter((_, i) => i !== idx))} className="text-slate-600 hover:text-red-400">
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-amber-400 text-xs font-semibold font-serif">{ab.ability_name}</p>
                  <p className="text-slate-400 text-xs mt-0.5 leading-relaxed">{ab.description}</p>
                  <p className="text-slate-600 text-xs mt-1 capitalize">{ab.ability_type}</p>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Main CharacterSheet ───────────────────────────────────────────────────
export default function CharacterSheet(): React.ReactElement {
  const { id: campaignId } = useParams<{ id: string }>()
  useAuth() // ensure auth context is mounted; redirects on 401

  const [characters,    setCharacters]    = useState<Character[]>([])
  const [activeIdx,     setActiveIdx]     = useState(0)
  const [editMode,      setEditMode]      = useState(false)
  const [draft,         setDraft]         = useState<Character | null>(null)
  const [isLoading,     setIsLoading]     = useState(true)
  const [isSaving,      setIsSaving]      = useState(false)
  const [error,         setError]         = useState<string | null>(null)
  const [activeTab,     setActiveTab]     = useState<'stats' | 'skills' | 'spells' | 'inventory' | 'abilities'>('stats')

  const character = characters[activeIdx] ?? null

  const fetchCharacters = useCallback(async () => {
    if (!campaignId) return
    setIsLoading(true)
    try {
      const data = await api.get<Character[]>(`/campaigns/${campaignId}/characters`)
      setCharacters(data)
    } catch {
      setError('Failed to load characters.')
    } finally {
      setIsLoading(false)
    }
  }, [campaignId])

  useEffect(() => { void fetchCharacters() }, [fetchCharacters])

  useEffect(() => {
    if (character && editMode) setDraft(JSON.parse(JSON.stringify(character)) as Character)
  }, [character, editMode])

  async function saveCharacter(): Promise<void> {
    if (!draft) return
    setIsSaving(true)
    setError(null)
    try {
      const updated = await api.put<Character>(
        `/campaigns/${campaignId}/characters/${draft.id}`,
        draft,
      )
      setCharacters((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
      setEditMode(false)
      setDraft(null)
    } catch {
      setError('Failed to save. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }

  function cancelEdit(): void {
    setEditMode(false)
    setDraft(null)
    setError(null)
  }

  const ch    = editMode ? draft : character
  const attrs = ch?.attributes ?? DEFAULT_ATTRS
  const stat  = ch?.status    ?? DEFAULT_STATUS

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-900 bg-dungeon-texture">
      {/* Nav */}
      <nav className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur border-b border-amber-700/30 px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to={`/campaign/${campaignId}`} className="btn-ghost py-1 px-2 text-xs">
            <ChevronLeft className="w-3.5 h-3.5" />
            Session
          </Link>
          <span className="text-slate-700">|</span>
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-amber-500" />
            <span className="font-serif text-amber-400">Characters</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!editMode ? (
            <button onClick={() => setEditMode(true)} className="btn-ghost py-1.5 text-xs">
              <Edit3 className="w-3.5 h-3.5" /> Edit
            </button>
          ) : (
            <>
              <button onClick={cancelEdit} className="btn-ghost py-1.5 text-xs">
                <X className="w-3.5 h-3.5" /> Cancel
              </button>
              <button onClick={saveCharacter} disabled={isSaving} className="btn-primary py-1.5 text-xs">
                {isSaving ? <Spinner size="sm" /> : <Save className="w-3.5 h-3.5" />}
                Save
              </button>
            </>
          )}
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {/* Character selector tabs */}
        {characters.length > 1 && (
          <div className="flex gap-2 mb-6">
            {characters.map((c, i) => (
              <button
                key={c.id}
                onClick={() => { setActiveIdx(i); setEditMode(false) }}
                className={`px-4 py-1.5 rounded-full text-xs font-serif border transition-all ${
                  i === activeIdx
                    ? 'bg-amber-600/30 border-amber-600/60 text-amber-300'
                    : 'border-slate-700 text-slate-500 hover:border-amber-700/40'
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 bg-red-900/40 border border-red-700/60 rounded-md px-4 py-3 mb-5 text-red-300 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {!ch ? (
          <div className="text-center py-20">
            <p className="text-slate-400 font-serif italic">No characters in this campaign yet.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* ── Header ── */}
            <div className="card-rune p-6">
              <div className="flex flex-col sm:flex-row gap-4 items-start justify-between">
                <div className="space-y-1">
                  {editMode && draft ? (
                    <input
                      value={draft.name}
                      onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                      className="input-dark text-2xl font-serif font-bold bg-transparent border-x-0 border-t-0 rounded-none px-0 py-1 text-amber-400"
                    />
                  ) : (
                    <h1 className="text-2xl font-serif text-amber-400">{ch.name}</h1>
                  )}
                  <p className="text-slate-400 text-sm font-serif">
                    {ch.race} ·{' '}
                    {ch.character_class}{ch.subclass ? ` (${ch.subclass})` : ''} ·{' '}
                    Level {ch.level}
                  </p>
                  <p className="text-slate-500 text-xs font-serif italic">{ch.alignment} · {ch.background}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <div className="stat-box">
                    <Shield className="w-3 h-3 text-blue-400" />
                    <p className="text-xl font-bold text-slate-100">{attrs.armor_class}</p>
                    <p className="text-xs text-slate-500">AC</p>
                  </div>
                  <div className="stat-box">
                    <Zap className="w-3 h-3 text-amber-400" />
                    <p className="text-xl font-bold text-slate-100">{attrs.speed}</p>
                    <p className="text-xs text-slate-500">Speed</p>
                  </div>
                  <div className="stat-box">
                    <Star className="w-3 h-3 text-yellow-400" />
                    <p className="text-xl font-bold text-slate-100">+{proficiencyBonus(ch.level)}</p>
                    <p className="text-xs text-slate-500">Prof</p>
                  </div>
                </div>
              </div>
            </div>

            {/* ── HP + Conditions ── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <HpTracker
                status={stat}
                edit={editMode}
                onChange={(s) => draft && setDraft({ ...draft, status: s })}
              />
              <ConditionsPanel
                conditions={stat.conditions}
                edit={editMode}
                onChange={(c) => draft && setDraft({ ...draft, status: { ...(draft.status ?? DEFAULT_STATUS), conditions: c } })}
              />
            </div>

            {/* ── Tabs ── */}
            <div className="border-b border-amber-700/30">
              <div className="flex gap-1 flex-wrap">
                {(['stats', 'skills', 'spells', 'inventory', 'abilities'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-2 text-xs font-serif capitalize border-b-2 transition-all -mb-px ${
                      activeTab === tab
                        ? 'border-amber-500 text-amber-400'
                        : 'border-transparent text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            {/* ── Tab content ── */}
            {activeTab === 'stats' && (
              <div className="space-y-4">
                {/* Ability scores */}
                <div className="card-rune p-4">
                  <h3 className="font-serif text-amber-400 text-sm tracking-wide mb-4">Ability Scores</h3>
                  <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                    {ABILITY_NAMES.map((ability) => (
                      <StatBox
                        key={ability}
                        name={ABILITY_SHORT[ability]}
                        score={attrs[ability]}
                        edit={editMode}
                        onChange={(v) =>
                          draft && setDraft({
                            ...draft,
                            attributes: { ...(draft.attributes ?? DEFAULT_ATTRS), [ability]: v },
                          })
                        }
                      />
                    ))}
                  </div>
                </div>

                {/* Saving throws */}
                <div className="card-rune p-4">
                  <h3 className="font-serif text-amber-400 text-sm tracking-wide mb-3">Saving Throws</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {ABILITY_NAMES.map((ability) => {
                      const prof = false
                      const base = abilityModifier(attrs[ability])
                      const total = base + (prof ? proficiencyBonus(ch.level) : 0)
                      return (
                        <div key={ability} className="flex items-center gap-2 text-sm">
                          <div className={`w-3 h-3 rounded-full border-2 ${prof ? 'bg-amber-500 border-amber-400' : 'border-slate-600'} shrink-0`} />
                          <span className="text-slate-300 text-xs">{ABILITY_SHORT[ability]}</span>
                          <span className="text-slate-400 text-xs ml-auto">{formatModifier(total)}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Appearance & Backstory */}
                <div className="card-rune p-4 grid grid-cols-1 gap-4 text-xs">
                  {([
                    ['Appearance', 'appearance'] as const,
                    ['Backstory',  'backstory']  as const,
                  ]).map(([label, field]) => (
                    <div key={field}>
                      <label className="label-rune">{label}</label>
                      {editMode && draft ? (
                        <textarea
                          value={draft[field] ?? ''}
                          onChange={(e) => setDraft({ ...draft, [field]: e.target.value })}
                          className="input-dark text-xs resize-none h-20"
                        />
                      ) : (
                        <p className="text-slate-400 font-serif italic leading-relaxed">{ch[field] || '—'}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'skills' && (
              <div className="card-rune p-4">
                <h3 className="font-serif text-amber-400 text-sm tracking-wide mb-3">Skills</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                  {Object.entries(SKILL_ABILITY).map(([skill, ability]) => {
                    const prof   = false
                    const base   = abilityModifier(attrs[ability])
                    const total  = base + (prof ? proficiencyBonus(ch.level) : 0)
                    const label  = skill.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
                    return (
                      <div key={skill} className="flex items-center gap-2 py-0.5 px-2 rounded hover:bg-slate-800/50">
                        <div className={`w-3 h-3 rounded-full border-2 shrink-0 ${prof ? 'bg-amber-500 border-amber-400' : 'border-slate-600'}`} />
                        <span className="text-slate-300 text-xs flex-1">{label}</span>
                        <span className="text-xs text-slate-500">{ABILITY_SHORT[ability]}</span>
                        <span className="text-slate-200 text-xs font-semibold w-8 text-right">{formatModifier(total)}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {activeTab === 'spells' && (
              <SpellSlotsPanel
                slots={stat.spell_slots}
                edit={editMode}
                onChange={(s) => draft && setDraft({ ...draft, status: { ...(draft.status ?? DEFAULT_STATUS), spell_slots: s } })}
              />
            )}

            {activeTab === 'inventory' && (
              <InventoryPanel
                items={ch.inventory}
                edit={editMode}
                onChange={(items) => draft && setDraft({ ...draft, inventory: items })}
              />
            )}

            {activeTab === 'abilities' && (
              <AbilitiesPanel
                abilities={ch.abilities}
                edit={editMode}
                onChange={(abilities) => draft && setDraft({ ...draft, abilities })}
              />
            )}

          </div>
        )}
      </main>
    </div>
  )
}
