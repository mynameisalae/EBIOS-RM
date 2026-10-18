/* eslint-disable @typescript-eslint/no-explicit-any */
import { ChevronRight } from 'lucide-react'
import { Fold, Kicker, LevelPill, Panel, Section, Tag, VDots } from '../../components/kit'

type O = Record<string, any>

const PHASES = ['Connaître', 'Rentrer', 'Trouver', 'Exploiter']
const PHASE_COLOR = ['bg-lvl-1', 'bg-lvl-2', 'bg-lvl-3', 'bg-lvl-4']
const phaseIndex = (p?: string) => Math.max(0, PHASES.indexOf(p ?? ''))

/** An attack, read top to bottom like a story: each step, the technique behind it, how likely it is. */
function Path({ path }: { path: O[] }) {
  return (
    <ol className="mt-6">
      {path.map((step, i) => {
        const p = phaseIndex(step.phase)
        return (
          <li key={i} className="flex gap-5">
            <div className="flex flex-col items-center">
              <span className={`mt-2 h-3.5 w-3.5 flex-none rounded-full ${PHASE_COLOR[p]}`} />
              {i < path.length - 1 && <span className="mt-1.5 w-[2px] flex-1 bg-line-strong" />}
            </div>
            <div className={`min-w-0 flex-1 ${i < path.length - 1 ? 'pb-8' : ''}`}>
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className="text-[12px] font-bold uppercase tracking-[0.14em] text-ink-mute">{step.phase}</span>
                <span className="mono font-bold text-ink">{step.technique_id || '—'}</span>
                <span className="font-semibold">{step.technique_name || 'Sans technique ATT&CK'}</span>
                <span className="ml-auto">
                  <VDots v={step.vraisemblance_action} title={`Cette étape : ${step.vraisemblance_action}`} />
                </span>
              </div>
              <p className="mt-1 max-w-[62ch] text-[16px] text-ink-soft">{step.description}</p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

function Mode({ s }: { s: O }) {
  return (
    <Fold
      lead={s.id}
      title={s.variante || s.id}
      right={
        <>
          {s.retenu && <Tag tone="crimson">Porte le risque</Tag>}
          <LevelPill level={s.revised_risk_level} />
        </>
      }
    >
      <p className="max-w-[62ch] text-ink-soft">{s.resume}</p>
      <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-[15px] text-ink-mute">
        {s.voie && <Tag>{String(s.voie).replace(/_/g, ' ')}</Tag>}
        <span className="inline-flex items-center gap-2">
          Vraisemblance <VDots v={s.vraisemblance_initiale} title="Vraisemblance initiale" />
          <ChevronRight className="h-4 w-4" />
          <VDots v={s.revised_likelihood} title="Après analyse des étapes" />
        </span>
      </div>
      <Path path={s.attack_path ?? []} />
    </Fold>
  )
}

export default function A4({ output }: { output: O }) {
  const scenarios: O[] = output.scenarios ?? []
  const steps = scenarios.flatMap((s) => s.attack_path ?? [])
  const counts = PHASES.map((p) => steps.filter((s: O) => s.phase === p).length)
  const total = counts.reduce((a, b) => a + b, 0) || 1
  const groups = [...new Set(scenarios.map((s) => s.scenario_strategique_id))]

  return (
    <>
      <Section title="Où se concentrent les attaques" aside="Du repérage jusqu’à l’impact">
        <div className="sheet px-10 py-9">
          <div className="flex h-5 overflow-hidden rounded-full">
            {counts.map((c, i) => (
              <div key={PHASES[i]} className={PHASE_COLOR[i]} style={{ width: `${(c / total) * 100}%` }} title={`${PHASES[i]} : ${c}`} />
            ))}
          </div>
          <ul className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
            {PHASES.map((p, i) => (
              <li key={p}>
                <p className="flex items-center gap-2 text-[15px] font-semibold">
                  <span className={`h-3 w-3 rounded-full ${PHASE_COLOR[i]}`} />
                  {p}
                </p>
                <p className="figure mt-1 text-[34px]">{counts[i]}</p>
                <p className="text-[14px] text-ink-mute">étape{counts[i] > 1 ? 's' : ''}</p>
              </li>
            ))}
          </ul>
        </div>
      </Section>

      {groups.map((g) => {
        const modes = scenarios.filter((s) => s.scenario_strategique_id === g)
        return (
          <Section
            key={g}
            title={
              <>
                Scénario stratégique <span className="mono text-[24px] text-crimson">{g}</span>
              </>
            }
            aside={`${modes.length} mode${modes.length > 1 ? 's' : ''} opératoire${modes.length > 1 ? 's' : ''}`}
          >
            <Panel>
              {modes.map((s) => (
                <Mode key={s.id} s={s} />
              ))}
            </Panel>
          </Section>
        )
      })}

      <p className="mt-10 max-w-[64ch] text-[15px] text-ink-mute">
        <Kicker>Lecture</Kicker>
        Chaque étape cite une technique réelle du référentiel MITRE ATT&CK, cotée en probabilité de succès et en difficulté. La vraisemblance d’un mode est celle de son maillon le plus faible.
      </p>
    </>
  )
}
