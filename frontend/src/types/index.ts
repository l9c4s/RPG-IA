// ─────────────────────────────────────────────
//  Utility types
// ─────────────────────────────────────────────
export type Nullable<T> = T | null

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
export type CampaignStatus = 'lobby' | 'active' | 'paused' | 'completed' | 'archived'

export interface Campaign {
  id: number
  title: string
  description: string
  rpg_system: string
  difficulty?: string
  tone?: string
  status: CampaignStatus
  owner_id: number
  created_at: string
  updated_at: string
  session_count?: number
  player_count?: number
}

export type CampaignStatusType = Campaign['status']

export interface CreateCampaignRequest {
  title: string
  description: string
  rpg_system: string
}

export interface Generated8BitCharacter {
  name?: string
  race?: string
  character_class?: string
  alignment?: string
  background?: string
  appearance?: string
  backstory?: string
  pixel_art_prompt: string
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
  source:      string
}

export type Condition =
  | 'Blinded'    | 'Charmed'     | 'Deafened'     | 'Exhaustion'
  | 'Frightened' | 'Grappled'    | 'Incapacitated'| 'Invisible'
  | 'Paralyzed'  | 'Petrified'   | 'Poisoned'     | 'Prone'
  | 'Restrained' | 'Stunned'     | 'Unconscious'

export interface CharacterStatus {
  hp_current:          number
  hp_max:              number
  hp_temp:             number
  conditions:          Condition[]
  spell_slots:         Record<string, number>
  exhaustion:          number
  death_saves_success: number
  death_saves_failure: number
}

export interface CharacterAttributes {
  strength:     number
  dexterity:    number
  constitution: number
  intelligence: number
  wisdom:       number
  charisma:     number
  armor_class:  number
  initiative:   number
  speed:        number
}

export interface Character {
  id:              string
  campaign_id?:    string
  player_id?:      string
  name:            string
  race:            string
  subrace?:        string
  character_class: string
  subclass?:       string
  level:           number
  proficiency_bonus: number
  alignment?:      string
  background?:     string
  personality_traits?: string
  ideals?:         string
  bonds?:          string
  flaws?:          string
  backstory?:      string
  appearance?:     string
  char_type:       string
  notes?:          string
  is_alive:        boolean
  status?:         CharacterStatus
  attributes?:     CharacterAttributes
  inventory:       InventoryItem[]
  abilities:       CharacterAbility[]
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
  session_id:    string
  character_id?: string
  action_type:   ActionType
  content:       string
  timestamp:     string
}

export interface DiceRoll {
  notation:  string
  result:    number
  breakdown: string
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
  x:           number
  y:           number
  type:        'city' | 'dungeon' | 'wilderness' | 'landmark' | 'unknown'
  is_current:  boolean
  discovered:  boolean
}
