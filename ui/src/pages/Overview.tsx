import { Link, useParams } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { api, useAsync, type AtelierOverview } from '../lib/api'
import { longDate, STATE_LABEL } from '../lib/format'
import { Failure, Loading, PageTitle, SectionTitle } from '../components/ui'

function ChainNode({ a, first, last }: { a: AtelierOverview; first: boolean; last: boolean }) {
  const done = a.state === 'approved'
  return (
    <div className="flex items-center">
      <span className={`h-[2px] flex-1 ${first ? 'bg-transparent' : done || a.state === 'in_progress' ? 'bg-crimson/70' : 'bg-line-strong'}`} />
      <span
        className={`flex h-9 w-9 items-center justify-center rounded-full border-2 font-display text-[14px] font-extrabold ${
          done ? 'border-crimson bg-crimson text-white' : a.state === 'in_progress' ? 'border-crimson bg-white text-crimson' : 'border-line-strong bg-white text-ink-mute'
        }`}
      >
        {a.n}
      </span>
      <span className={`h-[2px] flex-1 ${last ? 'bg-transparent' : 'bg-line-strong'}`} />
    </div>
  )
}

function AtelierCard({ id, a }: { id: string; a: AtelierOverview }) {
  const present = a.state !== 'absent'
  return (
    <Link
      to={`/missions/${id}/atelier/${a.n}`}
      className={`card group flex h-full flex-col p-5 transition-shadow hover:shadow-sheet ${present ? '' : 'bg-paper'}`}
    >
      <p className="font-display text-[17px] font-extrabold leading-tight text-ink group-hover:text-crimson">{a.label}</p>
      <p className="mt-2 text-[14px] italic leading-snug text-ink-mute">{a.question}</p>
      {present ? (
        <>
          <p className="mt-4 text-[14px] leading-snug text-ink-soft">{a.headline}</p>
          <dl className="mt-auto grid grid-cols-1 gap-2 pt-5">
            {a.metrics.map((m) => (
              <div key={m.label} className="flex items-baseline justify-between border-t border-line pt-2">
                <dt className="text-[13px] text-ink-mute">{m.label}</dt>
                <dd className="font-display text-[20px] font-extrabold text-ink">{m.value}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : (
        <p className="mt-auto pt-6 text-[13px] text-ink-mute">{STATE_LABEL.absent} dans cette base.</p>
      )}
      <p className={`mt-4 text-[12px] font-bold uppercase tracking-wider ${a.state === 'approved' ? 'text-ok' : 'text-ink-mute'}`}>
        {STATE_LABEL[a.state]}
        {a.version ? ` · v${a.version}` : ''}
      </p>
    </Link>
  )
}

function DocCard({ to, kicker, title, text }: { to: string; kicker: string; title: string; text: string }) {
  return (
    <Link to={to} className="card group flex items-start gap-5 p-6 transition-shadow hover:shadow-sheet">
      <div className="flex-1">
        <p className="eyebrow">{kicker}</p>
        <p className="mt-1 font-display text-[21px] font-extrabold text-ink group-hover:text-crimson">{title}</p>
        <p className="mt-2 text-[15px] text-ink-soft">{text}</p>
      </div>
      <ArrowRight className="mt-1 h-5 w-5 text-ink-mute transition-transform group-hover:translate-x-1 group-hover:text-crimson" />
    </Link>
  )
}

export default function Overview() {
  const { id = '' } = useParams()
  const { data, error, loading } = useAsync(() => api.mission(id), [id])
  if (loading) return <Loading />
  if (error || !data) return <Failure message={error} />

  const org = data.organisation.nom || data.mission.name
  const approved = data.ateliers.filter((a) => a.state === 'approved').length

  return (
    <>
      <PageTitle
        eyebrow={`Mission · ${data.mission.name}`}
        title={org}
        lead={data.organisation.secteur || undefined}
      />

      <div className="rise mb-2 flex flex-wrap gap-x-10 gap-y-2 text-[14px] text-ink-soft">
        <span>
          <b className="font-display text-[18px] font-extrabold text-ink">{approved}</b> atelier{approved > 1 ? 's' : ''} approuvé{approved > 1 ? 's' : ''} sur 5
        </span>
        <span>
          <b className="font-display text-[18px] font-extrabold text-ink">{data.decisions}</b> décision{data.decisions > 1 ? 's' : ''} de l’auditeur journalisée{data.decisions > 1 ? 's' : ''}
        </span>
        {data.attck_version && <span>Référentiel <span className="mono">{data.attck_version}</span></span>}
        <span>Mise à jour le {longDate(data.mission.updated_at)}</span>
      </div>

      <SectionTitle aside="Chaque atelier ne démarre qu’une fois le précédent approuvé">La chaîne d’analyse</SectionTitle>
      <div className="rise">
        <div className="hidden xl:grid xl:grid-cols-5 xl:gap-3">
          {data.ateliers.map((a, i) => (
            <ChainNode key={a.n} a={a} first={i === 0} last={i === data.ateliers.length - 1} />
          ))}
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {data.ateliers.map((a) => (
            <AtelierCard key={a.n} id={id} a={a} />
          ))}
        </div>
      </div>

      <SectionTitle aside="Deux documents, deux logiques">Les rapports</SectionTitle>
      <div className="rise grid gap-4 md:grid-cols-2">
        <DocCard
          to={`/missions/${id}/rapports`}
          kicker="Pour l’auditeur · sans IA"
          title="Annexe d’audit"
          text="Versions, décisions, provenance des écarts, événements anormaux — avec une case d’appréciation pour l’auditeur."
        />
        <DocCard
          to={`/missions/${id}/rapports`}
          kicker="Pour l’organisation · rédigé par l’IA"
          title="Rapport de mission"
          text="Le récit de l’étude, où chaque phrase renvoie aux champs qui la fondent et passe un contrôle automatique."
        />
      </div>
    </>
  )
}
