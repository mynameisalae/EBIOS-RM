import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { api, useAsync, type MissionSummary } from '../lib/api'
import { longDate } from '../lib/format'
import { Failure, Loading, PageHead } from '../components/kit'

function Chain({ ateliers }: { ateliers: MissionSummary['ateliers'] }) {
  return (
    <span className="inline-flex items-center" aria-label="Avancement par atelier">
      {ateliers.map((a, i) => (
        <span key={a.n} className="inline-flex items-center">
          {i > 0 && <span className={`h-[2px] w-5 ${a.state === 'absent' ? 'bg-line' : 'bg-crimson/50'}`} />}
          <span className={`h-3.5 w-3.5 rounded-full border-2 ${a.state === 'approved' ? 'border-crimson bg-crimson' : a.state === 'in_progress' ? 'border-crimson bg-white' : 'border-line-strong bg-white'}`} />
        </span>
      ))}
    </span>
  )
}

function Row({ m }: { m: MissionSummary }) {
  return (
    <Link to={`/missions/${m.id}`} className="rise sheet group flex flex-wrap items-center gap-x-10 gap-y-4 px-10 py-9 transition-shadow hover:shadow-sheet">
      <div className="min-w-[260px] flex-1">
        <p className="font-display text-[32px] font-extrabold leading-tight text-ink [font-stretch:108%] group-hover:text-crimson">{m.organisation}</p>
        <p className="mt-1 text-[16px] text-ink-mute">{m.secteur || m.name}</p>
      </div>
      <div className="flex flex-col items-start gap-3 sm:items-end">
        <Chain ateliers={m.ateliers} />
        <p className="text-[15px] text-ink-soft">
          <b className="font-bold text-ink">{m.approved}</b> atelier{m.approved > 1 ? 's' : ''} sur 5 · {longDate(m.updated_at)}
        </p>
      </div>
      <ArrowUpRight className="h-6 w-6 text-ink-mute transition-colors group-hover:text-crimson" />
    </Link>
  )
}

export default function Missions() {
  const { data, error, loading } = useAsync(api.missions, [])
  if (loading) return <Loading />
  if (error || !data) return <Failure message={error} />

  const worked = data.filter((m) => m.approved > 0).sort((a, b) => b.approved - a.approved || b.updated_at.localeCompare(a.updated_at))
  const preparing = data.filter((m) => m.approved === 0)

  return (
    <>
      <PageHead
        eyebrow="Analyse de risque · EBIOS Risk Manager"
        title="Vos missions"
        lead="De la collecte du contexte jusqu’au plan de traitement, cinq ateliers qui s’enchaînent. L’IA propose, le code vérifie, l’auditeur décide."
      />

      <div className="space-y-5">
        {worked.map((m) => (
          <Row key={m.id} m={m} />
        ))}
        {worked.length === 0 && <div className="sheet px-10 py-16 text-center text-ink-soft">Aucune mission n’a encore d’atelier approuvé dans cette base.</div>}
      </div>

      {preparing.length > 0 && (
        <details className="mt-14">
          <summary className="cursor-pointer text-[16px] font-semibold text-ink-mute hover:text-ink">
            {preparing.length} mission{preparing.length > 1 ? 's' : ''} en préparation (collecte du contexte)
          </summary>
          <div className="mt-5 space-y-2">
            {preparing.map((m) => (
              <Link key={m.id} to={`/missions/${m.id}`} className="sheet flex items-center justify-between gap-4 px-6 py-4 text-[15px] hover:shadow-sheet">
                <span className="font-semibold text-ink-soft">{m.organisation}</span>
                <span className="mono text-ink-mute">
                  {m.id.slice(0, 8)} · {longDate(m.updated_at)}
                </span>
              </Link>
            ))}
          </div>
        </details>
      )}
    </>
  )
}
