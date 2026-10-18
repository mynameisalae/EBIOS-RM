import { api, useAsync, type ProjectFacts } from '../lib/api'
import { longDate } from '../lib/format'
import { Failure, Loading, PageHead, Panel, Section } from '../components/kit'

function Figure({ value, label, detail }: { value: string | number; label: string; detail?: string }) {
  return (
    <div>
      <p className="figure text-[64px]">{value}</p>
      <p className="mt-3 text-[17px] font-semibold text-ink">{label}</p>
      {detail && <p className="text-[15px] text-ink-mute">{detail}</p>}
    </div>
  )
}

function Activity({ activity }: { activity: NonNullable<ProjectFacts['activity']> }) {
  const max = Math.max(...activity.weeks.map((w) => w.commits), 1)
  const bar = 34
  const width = activity.weeks.length * bar
  return (
    <div className="sheet px-10 py-9">
      <svg viewBox={`0 0 ${width} 130`} className="w-full" role="img" aria-label="Commits par semaine">
        {activity.weeks.map((w, i) => {
          const h = Math.max((w.commits / max) * 96, w.commits ? 4 : 0)
          return (
            <g key={w.week}>
              <rect x={i * bar + 5} y={104 - h} width={bar - 10} height={h} rx="3" fill={w.commits === max ? '#BE1E2D' : '#E3A83A'} opacity={w.commits === max ? 1 : 0.85}>
                <title>{`Semaine ${w.week} : ${w.commits} commits`}</title>
              </rect>
              <text x={i * bar + bar / 2} y={122} textAnchor="middle" fontSize="9" fill="#857F76" fontFamily="'JetBrains Mono Variable', monospace">
                {w.week}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="mt-3 text-[15px] text-ink-mute">
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
      <PageHead
        eyebrow="Le projet"
        title="Automatiser EBIOS Risk Manager, atelier par atelier"
        lead="Un agent qui conduit une analyse de risque cyber de bout en bout, de la collecte du contexte jusqu’au plan de traitement, sans jamais remplacer le jugement de l’auditeur."
      />

      <div className="rise-2 sheet grid gap-10 px-10 py-10 sm:grid-cols-2 lg:grid-cols-4">
        {weeks ? <Figure value={weeks} label="semaines de travail" detail={`${data.activity!.commits} commits`} /> : <Figure value={5} label="ateliers automatisés" />}
        <Figure value={data.frameworks.length} label="référentiels de conformité" detail={`${data.controls} contrôles évalués`} />
        {data.attack && <Figure value={data.attack.techniques} label="techniques MITRE ATT&CK" detail={`${data.attack.mitigations} mitigations · ${data.attack.version}`} />}
        <Figure value={2} label="rapports produits" detail="annexe d’audit · rapport de mission" />
      </div>

      <Section title="Trois principes">
        <div className="grid gap-10 md:grid-cols-3">
          {PRINCIPLES.map((p, i) => (
            <article key={p.t}>
              <p className="mono text-crimson">0{i + 1}</p>
              <h3 className="mt-2 text-[26px] font-extrabold leading-tight">{p.t}</h3>
              <p className="mt-3 text-[17px] text-ink-soft">{p.d}</p>
            </article>
          ))}
        </div>
      </Section>

      <Section title="La chaîne des cinq ateliers" aside="Chacun consomme le résultat approuvé du précédent">
        <Panel>
          {data.ateliers.map((a) => (
            <div key={a.n} className="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-line py-6 last:border-b-0">
              <span className="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-crimson font-display text-[17px] font-extrabold text-white">{a.n}</span>
              <p className="w-[260px] flex-none font-display text-[21px] font-extrabold [font-stretch:108%]">{a.label}</p>
              <p className="flex-1 text-[17px] italic text-ink-soft">{a.question}</p>
            </div>
          ))}
        </Panel>
      </Section>

      <Section title="Les référentiels évalués" aside="Lus depuis les plugins, sans toucher au code">
        <Panel>
          {data.frameworks.map((f) => (
            <div key={f.id} className="flex flex-wrap items-center gap-x-8 gap-y-3 border-b border-line py-6 last:border-b-0">
              <div className="min-w-[280px] flex-1">
                <p className="text-[18px] font-semibold">{f.name}</p>
                <p className="mono text-ink-mute">
                  {f.id} · version {f.version}
                </p>
              </div>
              <div className="flex w-[280px] items-center gap-4">
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-ground">
                  <div className="h-full rounded-full bg-gold" style={{ width: `${(f.controls / maxControls) * 100}%` }} />
                </div>
                <span className="w-28 text-right font-display text-[18px] font-extrabold">
                  {f.controls} <span className="text-[13px] font-semibold text-ink-mute">contrôles</span>
                </span>
              </div>
            </div>
          ))}
        </Panel>
      </Section>

      {data.activity && (
        <Section title="Le rythme du travail">
          <Activity activity={data.activity} />
        </Section>
      )}
    </>
  )
}
