// ─────────────────────────────────────────────
//  Auth
// ─────────────────────────────────────────────
export interface User {
  id: number
  username: string
  email: string
  is_active: boolean
  created_at: string
}

export interface Token {
  access_token: string
  token_type: 'bearer'
  user: User
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

// ─────────────────────────────────────────────
//  Campaigns
// ─────────────────────────────────────────────
export type CampaignStatus = 'active' | 'paused' | 'completed' | 'archived'

export interface Campaign {
  id: number
  title: string
  description: string
  rpg_system: string
  status: CampaignStatus
  owner_id: number
  created_at: string
  updated_at: string
  session_count?: number
  player_count?: number
}

export interface CreateCampaignRequest {
  title: string
  description: string
  rpg_system: string
}

// ─────────────────────────────────────────────
//  Characters
// ─────────────────────────────────────────────
export type Alignment =
  | 'Lawful Good'    | 'Neutral Good'   | 'Chaotic Good'
  | 'Lawful Neutral' | 'True Neutral'   | 'Chaotic Neutral'
  | 'Lawful Evil'    | 'Neutral Evil'   | 'Chaotic Evil'

export interface AbilityScores {
  strength:     number
  dexterity:    number
  constitution: number
  intelligence: number
  wisdom:       number
  charisma:     number
}

export interface SavingThrows {
  strength:     boolean
  dexterity:    boolean
  constitution: boolean
  intelligence: boolean
  wisdom:       boolean
  charisma:     boolean
}

export interface Skills {
  acrobatics:       boolean
  animal_handling:  boolean
  arcana:           boolean
  athletics:        boolean
  deception:        boolean
  history:          boolean
  insight:          boolean
  intimidation:     boolean
  investigation:    boolean
  medicine:         boolean
  nature:           boolean
  perception:       boolean
  performance:      boolean
  persuasion:       boolean
  religion:         boolean
  sleight_of_hand:  boolean
  stealth:          boolean
  survival:         boolean
}

export interface SpellSlots {
  level: number
  total: number
  used:  number
}

export interface InventoryItem {
  id:          string
  name:        string
  quantity:    number
  weight?:     number
  description?: string
  equipped:    boolean
}

export interface CharacterAbility {
  id:          string
  name:        string
  description: string
  source:      string   // e.g. "Class Feature", "Racial Trait", "Feat"
}

export type Condition =
  | 'Blinded'    | 'Charmed'     | 'Deafened'    | 'Exhaustion'
  | 'Frightened' | 'Grappled'    | 'Incapacitated'| 'Invisible'
  | 'Paralyzed'  | 'Petrified'   | 'Poisoned'    | 'Prone'
  | 'Restrained' | 'Stunned'     | 'Unconscious'

export interface CharacterStatus {
  hp_current:    number
  hp_max:        number
  hp_temp:       number
  ac:            number
  speed:         number
  initiative:    number
  death_saves_successes: number
  death_saves_failures:  number
  conditions:    Condition[]
  exhaustion_level: number
}

export interface Character {
  id:            number
  campaign_id:   number
  player_id:     number
  name:          string
  race:          string
  subrace?:      string
  character_class: string
  subclass?:     string
  level:         number
  experience:    number
  alignment:     Alignment
  background:    string
  personality_traits: string
  ideals:        string
  bonds:         string
  flaws:         string
  ability_scores:  AbilityScores
  saving_throws:   SavingThrows
  skills:          Skills
  spell_slots:     SpellSlots[]
  inventory:       InventoryItem[]
  abilities:       CharacterAbility[]
  status:          CharacterStatus
  notes:           string
  created_at:      string
  updated_at:      string
}

// ─────────────────────────────────────────────
//  Game Session / Actions
// ─────────────────────────────────────────────
export type ActionType =
  | 'free_action'
  | 'combat_action'
  | 'skill_check'
  | 'movement'
  | 'dialogue'
  | 'spell'
  | 'item_use'

export interface PlayerAction {
  session_id:    number
  character_id:  number
  action_type:   ActionType
  content:       string
  timestamp:     string
}

export interface DiceRoll {
  notation:  string   // e.g. "1d20+5"
  result:    number
  breakdown: string   // e.g. "13 + 5"
}

export interface StateUpdate {
  field:     string
  old_value: unknown
  new_value: unknown
  label:     string
}

export interface GMResponse {
  session_id:    number
  content:       string
  narration:     string
  dice_rolls?:   DiceRoll[]
  state_updates?: StateUpdate[]
  image_url?:    string
  audio_url?:    string
  timestamp:     string
}

export type ChatMessageRole = 'player' | 'gm' | 'system'

export interface ChatMessage {
  id:          string
  role:        ChatMessageRole
  content:     string
  timestamp:   string
  character_name?: string
  dice_rolls?: DiceRoll[]
  state_updates?: StateUpdate[]
  image_url?:  string
  audio_url?:  string
}

// ─────────────────────────────────────────────
//  Knowledge Bank
// ─────────────────────────────────────────────
export type PDFSourceType = 'rulebook' | 'sourcebook' | 'adventure' | 'supplement' | 'homebrew'
export type ProcessingStatus = 'pending' | 'processing' | 'done' | 'error'

export interface PDFSource {
  id:           number
  title:        string
  rpg_system:   string
  source_type:  PDFSourceType
  filename:     string
  status:       ProcessingStatus
  chunk_count:  number
  error_msg?:   string
  uploaded_at:  string
  processed_at?: string
}

export interface KnowledgeStats {
  total_chunks:     number
  total_sources:    number
  systems_covered:  string[]
  gm_is_ready:      boolean
  processing_count: number
  last_updated?:    string
}

// ─────────────────────────────────────────────
//  WebSocket messages
// ─────────────────────────────────────────────
export type WSMessageType =
  | 'player_action'
  | 'gm_response'
  | 'state_update'
  | 'system_message'
  | 'ping'
  | 'pong'
  | 'error'
  | 'gate_blocked'

export interface WSMessage {
  type:    WSMessageType
  payload: unknown
}

// ─────────────────────────────────────────────
//  Misc
// ─────────────────────────────────────────────
export interface ApiError {
  detail: string
  status?: number
}

export interface PaginatedResponse<T> {
  items:   T[]
  total:   number
  page:    number
  size:    number
  pages:   number
}

export interface Location {
  id:          string
  name:        string
  description: string
  x:           number   // SVG viewport percentage 0-100
  y:           number
  type:        'city' | 'dungeon' | 'wilderness' | 'landmark' | 'unknown'
  is_current:  boolean
  discovered:  boolean
}
