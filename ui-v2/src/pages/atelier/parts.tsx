import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { longDate } from '../../lib/format'
import { Kicker } from '../../components/kit'

/** Where the numbers of this atelier come from: its versions, newest last. */
export function Versions({ versions }: { versions: { number: number; status: string; created_at: string }[] }) {
  if (versions.length === 0) return null
  const label: Record<string, string> = { approved: 'approuvée', superseded: 'remplacée', current: 'en cours', rejected: 'refusée' }
  return (
    <section className="mt-24 border-t border-line pt-8">
      <Kicker>Historique des versions</Kicker>
      <ul className="mt-4 flex flex-wrap gap-x-8 gap-y-3 text-[15px]">
        {versions.map((v) => (
          <li key={v.number}>
            <span className="mono font-bold text-ink">v{v.number}</span>{' '}
            <span className={v.status === 'approved' ? 'font-semibold text-ok' : 'text-ink-soft'}>{label[v.status] ?? v.status}</span>
            <span className="text-ink-mute"> · {longDate(v.created_at)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

interface Check {
  controle: string
  statut: string
  message: string
}

/** The quality checker's verdict, one line per check — closed by default, never hidden. */
export function Quality({ report }: { report?: { checks?: Check[] } }) {
  const checks = report?.checks ?? []
  if (checks.length === 0) return null
  const ok = checks.filter((c) => c.statut === 'ok').length
  const dot: Record<string, string> = { ok: 'bg-ok', avertissement: 'bg-lvl-2', erreur: 'bg-crimson' }
  return (
    <details className="sheet mt-16 px-8 py-5">
      <summary className="cursor-pointer text-[16px] font-semibold text-ink-soft">
        Contrôle qualité automatique · {ok} point{ok > 1 ? 's' : ''} conforme{ok > 1 ? 's' : ''}
        {checks.length > ok ? ` · ${checks.length - ok} à examiner` : ''}
      </summary>
      <ul className="mt-5 space-y-3 text-[16px]">
        {checks.map((c, i) => (
          <li key={i} className="flex gap-4">
            <span className={`mt-[10px] h-2 w-2 shrink-0 rounded-full ${dot[c.statut] ?? 'bg-line-strong'}`} />
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

export function PrevNext({ id, n, labels }: { id: string; n: number; labels: string[] }) {
  const prev = n > 1 ? n - 1 : null
  const next = n < 5 ? n + 1 : null
  return (
    <nav className="mt-16 grid gap-6 sm:grid-cols-2">
      {prev ? (
        <Link to={`/missions/${id}/atelier/${prev}`} className="sheet group px-8 py-6 transition-shadow hover:shadow-sheet">
          <p className="flex items-center gap-2 text-[13px] font-bold uppercase tracking-[0.14em] text-ink-mute">
            <ArrowLeft className="h-4 w-4" /> Atelier {prev}
          </p>
          <p className="mt-1 font-display text-[20px] font-extrabold group-hover:text-crimson">{labels[prev - 1]}</p>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link to={`/missions/${id}/atelier/${next}`} className="sheet group px-8 py-6 text-right transition-shadow hover:shadow-sheet">
          <p className="flex items-center justify-end gap-2 text-[13px] font-bold uppercase tracking-[0.14em] text-ink-mute">
            Atelier {next} <ArrowRight className="h-4 w-4" />
          </p>
          <p className="mt-1 font-display text-[20px] font-extrabold group-hover:text-crimson">{labels[next - 1]}</p>
        </Link>
      ) : (
        <Link to={`/missions/${id}/rapports`} className="sheet group px-8 py-6 text-right transition-shadow hover:shadow-sheet sm:col-start-2">
          <p className="flex items-center justify-end gap-2 text-[13px] font-bold uppercase tracking-[0.14em] text-ink-mute">
            Pour finir <ArrowRight className="h-4 w-4" />
          </p>
          <p className="mt-1 font-display text-[20px] font-extrabold group-hover:text-crimson">Les rapports</p>
        </Link>
      )}
    </nav>
  )
}
