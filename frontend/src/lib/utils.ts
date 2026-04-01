/**
 * Combine class names, filtering out falsy values.
 */
export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ')
}

/**
 * Calculate the D&D ability modifier from an ability score.
 */
export function dndModifier(score: number): number {
  return Math.floor((score - 10) / 2)
}

/**
 * Format a D&D ability score modifier with its sign (+3, -1, +0).
 */
export function formatModifier(score: number): string {
  const mod = dndModifier(score)
  return mod >= 0 ? `+${mod}` : `${mod}`
}

/**
 * Format a date string or Date object to Brazilian locale (dd/mm/yyyy).
 */
export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString('pt-BR', {
    day:   '2-digit',
    month: '2-digit',
    year:  'numeric',
  })
}

/**
 * Truncate a string to `max` characters, appending ellipsis if needed.
 */
export function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max) + '…' : str
}

/**
 * Return the singular or plural form based on count.
 */
export function pluralize(n: number, singular: string, plural: string): string {
  return n === 1 ? singular : plural
}
