// ─────────────────────────────────────────────
//  Utility types
// ─────────────────────────────────────────────
export type Nullable<T> = T | null

// ─────────────────────────────────────────────
//  Auth
// ─────────────────────────────────────────────
export interface User {
  id: string
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
export type InitStatus     = 'idle' | 'generating' | 'ready' | 'failed'

export interface Campaign {
  id:               string
  title:            string
  description:      string | null
  rpg_system:       string
  difficulty:       string
  tone:             string
  status:           CampaignStatus
  init_status:      InitStatus
  opening_generated: boolean
  owner_id?:        string
  created_at:       string
  updated_at:       string
  session_count?:   number
  player_count?:    number
}

export type CampaignStatusType = Campaign['status']

export interface CreateCampaignRequest {
  title:       string
  description: string
  rpg_system:  string
  difficulty?: string
  tone?:       string
}

// ─────────────────────────────────────────────
//  Characters
// ─────────────────────────────────────────────
export interface CharacterAttributes {
  id:           string
  character_id: string
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

export interface CharacterStatus {
  id:                  string
  character_id:        string
  hp_max:              number
  hp_current:          number
  hp_temp:             number
  conditions:          string[]
  spell_slots:         Record<string, number>
  exhaustion:          number
  death_saves_success: number
  death_saves_failure: number
  updated_at:          string
}

export interface InventoryItem {
  id:           string
  character_id: string
  item_name:    string
  item_type:    string
  quantity:     number
  weight:       number
  value_gp:     number
  properties:   Record<string, unknown>
  equipped:     boolean
  created_at:   string
}

export interface CharacterAbility {
  id:              string
  character_id:    string
  ability_name:    string
  ability_type:    string
  description:     string | null
  spell_level:     number | null
  uses_max:        number | null
  uses_remaining:  number | null
  recharge:        string | null
}

export interface Character {
  id:               string
  name:             string
  race:             string
  character_class:  string
  subclass?:        string | null
  level:            number
  proficiency_bonus: number
  background:       string | null
  alignment:        string | null
  char_type:        'player' | 'npc' | 'ai_companion'
  backstory:        string | null
  appearance:       string | null
  campaign_id:      string | null
  owner_id:         string | null
  is_alive:         boolean
  created_at:       string
  updated_at:       string
  status?:          CharacterStatus | null
  attributes?:      CharacterAttributes | null
  inventory:        InventoryItem[]
  abilities:        CharacterAbility[]
}

// ─────────────────────────────────────────────
//  Game Session / Actions
// ─────────────────────────────────────────────
export interface DiceRoll {
  expr:      string
  result:    number
  breakdown: string
}

export interface StateUpdate {
  field: string
  value: string
}

export type ChatMessageRole =
  | 'player'
  | 'gm'
  | 'gm_opening'
  | 'ai_companion'
  | 'system'

export interface ChatMessage {
  id:              string
  role:            ChatMessageRole
  content:         string
  timestamp:       string
  character_name?: string
  dice_rolls?:     DiceRoll[]
  state_updates?:  StateUpdate[]
  image_url?:      string
  audio_url?:      string
}

// ─────────────────────────────────────────────
//  Knowledge Bank
// ─────────────────────────────────────────────
export type PDFSourceType    = 'rulebook' | 'sourcebook' | 'adventure' | 'supplement' | 'homebrew'
export type ProcessingStatus = 'pending' | 'processing' | 'done' | 'error'

export interface PDFSource {
  id:            string
  title:         string
  rpg_system:    string
  source_type:   PDFSourceType
  filename:      string
  status:        ProcessingStatus
  chunk_count:   number
  error_msg?:    string
  uploaded_at:   string
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
  | 'companion_reaction'
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
  detail:  string
  status?: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page:  number
  size:  number
  pages: number
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
