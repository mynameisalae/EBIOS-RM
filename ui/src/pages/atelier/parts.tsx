import type { ReactNode } from 'react'
import { longDate } from '../../lib/format'

const GRAVITY = ['Minimale', 'Significative', 'Grave', 'Critique']
const GRAVITY_STYLE = ['bg-line text-ink-soft', 'bg-lvl-1 text-ink', 'bg-lvl-2 text-ink', 'bg-lvl-3 text-white', 'bg-lvl-4 text-white']

export function GravityPill({ g }: { g?: string }) {
  if (!g) return null
  const i = GRAVITY.indexOf(g) + 1
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-[12px] font-bold ${GRAVITY_STYLE[i]}`} title="Gravité (Minimale < Significative < Grave < Critique)">{g}</span>
}

export function Tag({ children, tone = 'plain' }: { children: ReactNode; tone?: 'plain' | 'crimson' | 'gold' }) {
  const tones = {
    plain: 'border-line bg-white text-ink-soft',
    crimson: 'border-crimson/25 bg-crimson-tint text-crimson-deep',
    gold: 'border-gold/30 bg-gold-tint text-gold-deep',
  }
  return <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[12px] font-semibold ${tones[tone]}`}>{children}</span>
}

export function Kicker({ children }: { children: ReactNode }) {
  return <p className="text-[12px] font-bold uppercase tracking-[0.12em] text-ink-mute">{children}</p>
}

/** Where the numbers of this atelier come from: its versions, newest last. */
export function Versions({ versions }: { versions: { number: number; status: string; created_at: string }[] }) {
  if (versions.length === 0) return null
  const label: Record<string, string> = { approved: 'approuvée', superseded: 'remplacée', current: 'en cours', rejected: 'refusée' }
  return (
    <div className="mt-14 border-t border-line pt-5">
      <Kicker>Historique des versions</Kicker>
      <ul className="mt-3 flex flex-wrap gap-2">
        {versions.map((v) => (
          <li key={v.number} className="chip">
            <span className="mono font-bold text-ink">v{v.number}</span>
            <span className={v.status === 'approved' ? 'text-ok' : ''}>{label[v.status] ?? v.status}</span>
            <span className="text-ink-mute">· {longDate(v.created_at)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

interface Check { controle: string; statut: string; message: string }

/** The quality checker's verdict, one line per check — closed by default, never hidden. */
export function Quality({ report }: { report?: { checks?: Check[] } }) {
  const checks = report?.checks ?? []
  if (checks.length === 0) return null
  const ok = checks.filter((c) => c.statut === 'ok').length
  const dot: Record<string, string> = { ok: 'bg-ok', avertissement: 'bg-lvl-2', erreur: 'bg-crimson' }
  return (
    <details className="mt-6 rounded-xl border border-line bg-white px-5 py-3">
      <summary className="cursor-pointer text-[14px] font-semibold text-ink-soft">
        Contrôle qualité automatique · {ok} point{ok > 1 ? 's' : ''} conforme{ok > 1 ? 's' : ''}
        {checks.length > ok ? ` · ${checks.length - ok} à examiner` : ''}
      </summary>
      <ul className="mt-3 space-y-2 text-[14px]">
        {checks.map((c, i) => (
          <li key={i} className="flex gap-3">
            <span className={`mt-[7px] h-2 w-2 shrink-0 rounded-full ${dot[c.statut] ?? 'bg-line-strong'}`} />
            <span>
              <b className="font-semibold text-ink">{c.controle}</b>
              <span className="text-ink-soft"> — {c.message}</span>
            </span>
          </li>
        ))}
      </ul>
    </details>
  )
}

export function Grid({ children, cols = 2 }: { children: ReactNode; cols?: 2 | 3 }) {
  return <div className={`grid gap-4 ${cols === 3 ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>{children}</div>
}
