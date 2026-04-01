export const RPG_SYSTEMS = [
  'D&D 5e',
  'Pathfinder 2e',
  'Call of Cthulhu',
  'Vampire: The Masquerade',
  'Shadowrun',
  'Custom',
] as const

export const DIFFICULTIES = ['easy', 'medium', 'hard'] as const

export const DIFFICULTY_LABELS = {
  easy:   'Fácil',
  medium: 'Médio',
  hard:   'Difícil',
} as const

export const ALIGNMENTS = [
  'Leal e Bom',
  'Neutro e Bom',
  'Caótico e Bom',
  'Leal e Neutro',
  'Neutro',
  'Caótico e Neutro',
  'Leal e Mau',
  'Neutro e Mau',
  'Caótico e Mau',
] as const

export const RACES = [
  'Humano',
  'Elfo',
  'Anão',
  'Halfling',
  'Gnomo',
  'Meio-Elfo',
  'Meio-Orc',
  'Tiefling',
  'Draconato',
] as const

export const CLASSES = [
  'Bárbaro',
  'Bardo',
  'Clérigo',
  'Druida',
  'Guerreiro',
  'Monge',
  'Paladino',
  'Patrulheiro',
  'Ladino',
  'Feiticeiro',
  'Bruxo',
  'Mago',
] as const

export const ABILITY_SCORES = ['str', 'dex', 'con', 'int', 'wis', 'cha'] as const

export const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8] as const

export const CONDITIONS = [
  'Amedrontado',
  'Agarrado',
  'Atordoado',
  'Caído',
  'Cego',
  'Enfeitiçado',
  'Envenenado',
  'Exausto',
  'Incapacitado',
  'Inconsciente',
  'Invisível',
  'Paralisado',
  'Petrificado',
  'Restrito',
  'Surdo',
] as const

export const SKILLS = [
  { name: 'Acrobacia',         ability: 'dex' },
  { name: 'Arcanismo',         ability: 'int' },
  { name: 'Atletismo',         ability: 'str' },
  { name: 'Atuação',           ability: 'cha' },
  { name: 'Enganação',         ability: 'cha' },
  { name: 'Furtividade',       ability: 'dex' },
  { name: 'História',          ability: 'int' },
  { name: 'Intimidação',       ability: 'cha' },
  { name: 'Intuição',          ability: 'wis' },
  { name: 'Investigação',      ability: 'int' },
  { name: 'Lidar com Animais', ability: 'wis' },
  { name: 'Medicina',          ability: 'wis' },
  { name: 'Natureza',          ability: 'int' },
  { name: 'Percepção',         ability: 'wis' },
  { name: 'Persuasão',         ability: 'cha' },
  { name: 'Prestidigitação',   ability: 'dex' },
  { name: 'Religião',          ability: 'int' },
  { name: 'Sobrevivência',     ability: 'wis' },
] as const
