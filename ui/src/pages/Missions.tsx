import { Link } from 'react-router-dom'
import { api, useAsync, type MissionSummary } from '../lib/api'
import { longDate } from '../lib/format'
import { Failure, Loading, MiniChain, PageTitle } from '../components/ui'

function MissionRow({ m }: { m: MissionSummary }) {
  return (
    <Link
      to={`/missions/${m.id}`}
      className="card rise group flex flex-wrap items-center gap-x-8 gap-y-3 px-7 py-6 transition-shadow hover:shadow-sheet"
    >
      <div className="min-w-[220px] flex-1">
        <p className="font-display text-[24px] font-extrabold leading-tight text-ink group-hover:text-crimson">{m.organisation}</p>
        <p className="mt-1 text-[14px] text-ink-soft">
          {m.secteur ? `${m.secteur} · ` : ''}
          <span className="mono text-ink-mute">{m.name}</span>
        </p>
      </div>
      <MiniChain ateliers={m.ateliers} />
      <div className="w-[230px] text-right">
        <p className="font-display text-[18px] font-extrabold text-ink">
          {m.approved}
          <span className="text-ink-mute"> / 5</span>
        </p>
        <p className="text-[13px] text-ink-mute">ateliers approuvés · {longDate(m.updated_at)}</p>
      </div>
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
      <PageTitle
        eyebrow="Analyse de risque · EBIOS Risk Manager"
        title="Missions"
        lead="Chaque mission suit la chaîne des cinq ateliers, de la collecte jusqu’au plan de traitement. L’IA propose, le code vérifie, l’auditeur décide : un atelier n’ouvre que lorsque le précédent est approuvé."
      />

      {worked.length > 0 && (
        <div className="space-y-4">
          {worked.map((m) => (
            <MissionRow key={m.id} m={m} />
          ))}
        </div>
      )}

      {worked.length === 0 && (
        <div className="card px-8 py-12 text-center text-ink-soft">
          Aucune mission n’a encore d’atelier approuvé dans cette base.
        </div>
      )}

      {preparing.length > 0 && (
        <details className="mt-10">
          <summary className="cursor-pointer text-[14px] font-semibold text-ink-mute hover:text-ink">
            {preparing.length} mission{preparing.length > 1 ? 's' : ''} en préparation (collecte du contexte)
          </summary>
          <div className="mt-4 space-y-3">
            {preparing.map((m) => (
              <Link key={m.id} to={`/missions/${m.id}`} className="card flex items-center justify-between gap-4 px-5 py-3 text-[14px] hover:border-ink-mute">
                <span className="font-semibold text-ink-soft">{m.organisation}</span>
                <span className="mono text-ink-mute">{m.id.slice(0, 8)} · {longDate(m.updated_at)}</span>
              </Link>
            ))}
          </div>
        </details>
      )}
    </>
  )
}
