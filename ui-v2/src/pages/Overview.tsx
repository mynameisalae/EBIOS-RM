import { Link, useParams } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { api, useAsync, type AtelierOverview } from '../lib/api'
import { longDate, STATE_LABEL } from '../lib/format'
import { Failure, Kicker, Loading, PageHead, Section } from '../components/kit'

function Row({ id, a, last }: { id: string; a: AtelierOverview; last: boolean }) {
  const present = a.state !== 'absent'
  const done = a.state === 'approved'
  return (
    <li className="relative flex gap-8">
      <div className="flex flex-col items-center">
        <span
          className={`z-10 flex h-14 w-14 flex-none items-center justify-center rounded-full border-2 font-display text-[22px] font-extrabold [font-stretch:118%] ${
            done ? 'border-crimson bg-crimson text-white' : present ? 'border-crimson bg-white text-crimson' : 'border-line-strong bg-white text-ink-mute'
          }`}
        >
          {a.n}
        </span>
        {!last && <span className={`w-[2px] flex-1 ${done ? 'bg-crimson/40' : 'bg-line-strong'}`} />}
      </div>
      <Link
        to={`/missions/${id}/atelier/${a.n}`}
        className={`group mb-8 flex-1 rounded-2xl px-8 py-7 transition-shadow ${present ? 'sheet hover:shadow-sheet' : 'border border-dashed border-line-strong'}`}
      >
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-1">
          <h3 className="text-[26px] font-extrabold leading-tight group-hover:text-crimson">{a.label}</h3>
          <span className={`pt-1.5 text-[12px] font-bold uppercase tracking-[0.14em] ${done ? 'text-ok' : 'text-ink-mute'}`}>
            {STATE_LABEL[a.state]}
            {a.version ? ` · v${a.version}` : ''}
          </span>
        </div>
        <p className="mt-1 text-[17px] italic text-ink-mute">{a.question}</p>
        {present ? (
          <>
            <p className="mt-5 max-w-[56ch] text-[18px] text-ink-soft">{a.headline}</p>
            <dl className="mt-6 flex flex-wrap gap-x-12 gap-y-4">
              {a.metrics.map((m) => (
                <div key={m.label}>
                  <dd className="figure text-[36px]">{m.value}</dd>
                  <dt className="mt-1 text-[14px] text-ink-mute">{m.label}</dt>
                </div>
              ))}
            </dl>
          </>
        ) : (
          <p className="mt-4 text-[15px] text-ink-mute">Pas encore de résultats pour cet atelier dans cette base.</p>
        )}
      </Link>
    </li>
  )
}

function Doc({ to, kicker, title, text }: { to: string; kicker: string; title: string; text: string }) {
  return (
    <Link to={to} className="sheet group flex flex-col px-9 py-8 transition-shadow hover:shadow-sheet">
      <p className="eyebrow">{kicker}</p>
      <p className="mt-3 font-display text-[28px] font-extrabold leading-tight group-hover:text-crimson [font-stretch:108%]">{title}</p>
      <p className="mt-3 flex-1 text-[17px] text-ink-soft">{text}</p>
      <span className="mt-6 inline-flex items-center gap-2 text-[15px] font-semibold text-crimson">
        Ouvrir <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
      </span>
    </Link>
  )
}

export default function Overview() {
  const { id = '' } = useParams()
  const { data, error, loading } = useAsync(() => api.mission(id), [id])
  if (loading) return <Loading />
  if (error || !data) return <Failure message={error} />

  const approved = data.ateliers.filter((a) => a.state === 'approved').length

  return (
    <>
      <PageHead eyebrow={`Mission · ${data.mission.name}`} title={data.organisation.nom || data.mission.name} lead={data.organisation.secteur || undefined} size="xl" />

      <div className="rise-2 sheet grid gap-y-6 px-10 py-8 sm:grid-cols-3">
        <div>
          <p className="figure text-[44px]">
            {approved}
            <span className="text-ink-mute"> / 5</span>
          </p>
          <Kicker>ateliers approuvés</Kicker>
        </div>
        <div>
          <p className="figure text-[44px]">{data.decisions}</p>
          <Kicker>décisions journalisées</Kicker>
        </div>
        <div>
          <p className="figure text-[44px]">{data.model_calls}</p>
          <Kicker>appels au modèle</Kicker>
        </div>
      </div>

      <Section title="La chaîne d’analyse" aside="Un atelier ne démarre qu’une fois le précédent approuvé">
        <ol>
          {data.ateliers.map((a, i) => (
            <Row key={a.n} id={id} a={a} last={i === data.ateliers.length - 1} />
          ))}
        </ol>
      </Section>

      <Section title="Les rapports" aside={`Mis à jour le ${longDate(data.mission.updated_at)}`}>
        <div className="grid gap-6 md:grid-cols-2">
          <Doc
            to={`/missions/${id}/rapports`}
            kicker="Pour l’auditeur · sans IA"
            title="Annexe d’audit"
            text="Versions, décisions, provenance des écarts, événements anormaux — avec une case d’appréciation pour l’auditeur."
          />
          <Doc
            to={`/missions/${id}/rapports`}
            kicker="Pour l’organisation · rédigé par l’IA"
            title="Rapport de mission"
            text="Le récit de l’étude : chaque phrase renvoie aux champs qui la fondent et passe un contrôle automatique."
          />
        </div>
      </Section>
    </>
  )
}
