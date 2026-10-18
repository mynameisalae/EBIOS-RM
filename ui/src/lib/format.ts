export const LEVELS = ['Faible', 'Moyen', 'Élevé', 'Critique'] as const

export function levelIndex(level?: string): number {
  const i = LEVELS.indexOf((level ?? '') as (typeof LEVELS)[number])
  return i < 0 ? 0 : i + 1
}

export function vIndex(v?: string): number {
  const m = /^V([1-4])$/.exec(v ?? '')
  return m ? Number(m[1]) : 0
}

export function longDate(iso?: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
}

export function shortDate(iso?: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
}

export const STATE_LABEL = { approved: 'Approuvé', in_progress: 'En cours', absent: 'Pas de résultats' } as const
