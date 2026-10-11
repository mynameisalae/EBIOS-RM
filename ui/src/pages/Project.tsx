import { api, useAsync, type ProjectFacts } from '../lib/api'
import { longDate } from '../lib/format'
import { Failure, Loading, PageTitle, SectionTitle } from '../components/ui'

function Figure({ value, label, detail }: { value: string | number; label: string; detail?: string }) {
  return (
    <div className="border-l border-line-strong pl-5">
      <p className="font-display text-[44px] font-extrabold leading-none text-ink">{value}</p>
      <p className="mt-2 text-[14px] font-semibold text-ink">{label}</p>
      {detail && <p className="text-[13px] text-ink-mute">{detail}</p>}
    </div>
  )
}

function Activity({ activity }: { activity: NonNullable<ProjectFacts['activity']> }) {
  const max = Math.max(...activity.weeks.map((w) => w.commits), 1)
  const bar = 34
  const width = activity.weeks.length * bar
  return (
    <div className="card p-6">
      <svg viewBox={`0 0 ${width} 130`} className="w-full" role="img" aria-label="Commits par semaine">
        {activity.weeks.map((w, i) => {
          const h = Math.max((w.commits / max) * 96, w.commits ? 4 : 0)
          return (
            <g key={w.week}>
              <rect x={i * bar + 5} y={104 - h} width={bar - 10} height={h} rx="3" fill={w.commits === max ? '#BE1E2D' : '#E3A83A'} opacity={w.commits === max ? 1 : 0.85}>
                <title>{`Semaine ${w.week} : ${w.commits} commits`}</title>
              </rect>
              <text x={i * bar + bar / 2} y={122} textAnchor="middle" fontSize="9" fill="#8B857D" fontFamily="'JetBrains Mono Variable', monospace">
                {w.week}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="mt-2 text-[13px] text-ink-mute">
        Activité du dépôt semaine par semaine, du {longDate(activity.first)} au {longDate(activity.last)}.
      </p>
    </div>
  )
}

const PRINCIPLES = [
  { t: 'L’IA propose', d: 'Elle lit le contexte, rédige, signale et explique. Elle n’invente aucun fait sur l’organisation et ne décide rien.' },
  { t: 'Le code vérifie', d: 'Chaque réponse du modèle passe par des schémas stricts et des contrôles : un identifiant, une technique ou une mesure qui n’existe pas est refusé.' },
  { t: 'L’auditeur décide', d: 'Chaque atelier est approuvé par un humain avant le suivant, et chaque décision est journalisée avec sa justification.' },
]

export default function Project() {
  const { data, error, loading } = useAsync(api.project, [])
  if (loading) return <Loading />
  if (error || !data) return <Failure message={error} />

  const weeks = data.activity?.weeks.length
  const maxControls = Math.max(...data.frameworks.map((f) => f.controls), 1)

  return (
    <>
      <PageTitle
        eyebrow="Le projet"
        title="Automatiser EBIOS Risk Manager, atelier par atelier"
        lead="Un agent qui conduit une analyse de risque cyber de bout en bout, de la collecte du contexte jusqu’au plan de traitement, sans jamais remplacer le jugement de l’auditeur."
      />

      <div className="rise grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
        {weeks ? <Figure value={weeks} label="semaines de travail" detail={`${data.activity!.commits} commits`} /> : <Figure value={5} label="ateliers automatisés" />}
        <Figure value={data.frameworks.length} label="référentiels de conformité" detail={`${data.controls} contrôles évalués`} />
        {data.attack && <Figure value={data.attack.techniques} label="techniques MITRE ATT&CK" detail={`${data.attack.mitigations} mitigations · ${data.attack.version}`} />}
        <Figure value={2} label="rapports produits" detail="annexe d’audit · rapport de mission" />
      </div>

      <SectionTitle>Trois principes</SectionTitle>
      <div className="grid gap-5 md:grid-cols-3">
        {PRINCIPLES.map((p, i) => (
          <article key={p.t} className="rise">
            <p className="mono text-crimson">0{i + 1}</p>
            <h3 className="mt-1 text-[22px] font-extrabold leading-tight">{p.t}</h3>
            <p className="mt-2 text-[15px] text-ink-soft">{p.d}</p>
          </article>
        ))}
      </div>

      <SectionTitle aside="Chacun consomme le résultat approuvé du précédent">La chaîne des cinq ateliers</SectionTitle>
      <ol className="card divide-y divide-line">
        {data.ateliers.map((a) => (
          <li key={a.n} className="flex items-center gap-5 px-6 py-4">
            <span className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-crimson font-display text-[14px] font-extrabold text-white">{a.n}</span>
            <p className="w-[220px] flex-none font-display text-[17px] font-extrabold">{a.label}</p>
            <p className="text-[15px] italic text-ink-soft">{a.question}</p>
          </li>
        ))}
      </ol>

      <SectionTitle aside="Lus depuis les plugins, sans toucher au code">Les référentiels évalués</SectionTitle>
      <div className="card divide-y divide-line">
        {data.frameworks.map((f) => (
          <div key={f.id} className="flex flex-wrap items-center gap-x-6 gap-y-2 px-6 py-4">
            <div className="min-w-[280px] flex-1">
              <p className="text-[15px] font-semibold">{f.name}</p>
              <p className="mono text-ink-mute">{f.id} · version {f.version}</p>
            </div>
            <div className="flex w-[260px] items-center gap-3">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-line">
                <div className="h-full rounded-full bg-gold" style={{ width: `${(f.controls / maxControls) * 100}%` }} />
              </div>
              <span className="w-24 text-right font-display text-[15px] font-extrabold">{f.controls} <span className="text-[12px] font-semibold text-ink-mute">contrôles</span></span>
            </div>
          </div>
        ))}
      </div>

      {data.activity && (
        <>
          <SectionTitle>Le rythme du travail</SectionTitle>
          <Activity activity={data.activity} />
        </>
      )}
    </>
  )
}
