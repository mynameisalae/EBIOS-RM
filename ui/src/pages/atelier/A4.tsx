/* eslint-disable @typescript-eslint/no-explicit-any */
import { ChevronRight } from 'lucide-react'
import { LevelPill, SectionTitle, VDots } from '../../components/ui'
import { Kicker, Tag } from './parts'

type O = Record<string, any>

const PHASES = ['Connaître', 'Rentrer', 'Trouver', 'Exploiter']
const PHASE_COLOR = ['bg-lvl-1', 'bg-lvl-2', 'bg-lvl-3', 'bg-lvl-4']
const phaseIndex = (p?: string) => Math.max(0, PHASES.indexOf(p ?? ''))

function Step({ step, n }: { step: O; n: number }) {
  const p = phaseIndex(step.phase)
  return (
    <div className="flex w-[216px] flex-none flex-col rounded-lg border border-line bg-paper p-3.5">
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${PHASE_COLOR[p]}`} />
        <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-ink-soft">{step.phase}</span>
        <span className="mono ml-auto text-ink-mute">{n}</span>
      </div>
      <p className="mono mt-3 text-[14px] font-bold text-ink">{step.technique_id || '—'}</p>
      <p className="text-[13px] font-semibold leading-snug text-ink">{step.technique_name || 'Sans technique ATT&CK'}</p>
      <p className="mt-2 line-clamp-4 text-[13px] leading-snug text-ink-soft">{step.description}</p>
      <div className="mt-auto pt-3">
        <VDots v={step.vraisemblance_action} title={`Cette étape : ${step.vraisemblance_action}`} />
      </div>
    </div>
  )
}

function Mode({ s }: { s: O }) {
  const path: O[] = s.attack_path ?? []
  return (
    <article className="card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-[260px] flex-1">
          <p className="flex items-center gap-2">
            <span className="mono font-bold text-crimson">{s.id}</span>
            {s.voie && <Tag>{String(s.voie).replace(/_/g, ' ')}</Tag>}
            {s.retenu && <Tag tone="crimson">Porte le risque</Tag>}
          </p>
          <h3 className="mt-1.5 text-[20px] font-extrabold leading-tight">{s.variante || s.id}</h3>
          <p className="mt-2 max-w-[70ch] text-[15px] text-ink-soft">{s.resume}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <LevelPill level={s.revised_risk_level} size="lg" />
          <span className="flex items-center gap-2 text-[13px] text-ink-mute">
            <VDots v={s.vraisemblance_initiale} title="Vraisemblance initiale" />
            <ChevronRight className="h-3.5 w-3.5" />
            <VDots v={s.revised_likelihood} title="Vraisemblance après analyse des étapes" />
          </span>
        </div>
      </div>
      <div className="mt-5 flex items-stretch gap-1 overflow-x-auto pb-2">
        {path.map((step, i) => (
          <div key={i} className="flex items-stretch gap-1">
            {i > 0 && <ChevronRight className="my-auto h-4 w-4 flex-none text-ink-mute" />}
            <Step step={step} n={i + 1} />
          </div>
        ))}
      </div>
    </article>
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
      <SectionTitle aside={`${steps.length} étapes · ${new Set(steps.map((s: O) => s.technique_id).filter(Boolean)).size} techniques ATT&CK distinctes`}>
        Où se concentrent les attaques
      </SectionTitle>
      <div className="card p-6">
        <div className="flex h-4 overflow-hidden rounded-full">
          {counts.map((c, i) => (
            <div key={PHASES[i]} className={PHASE_COLOR[i]} style={{ width: `${(c / total) * 100}%` }} title={`${PHASES[i]} : ${c}`} />
          ))}
        </div>
        <ul className="mt-4 flex flex-wrap gap-x-8 gap-y-2">
          {PHASES.map((p, i) => (
            <li key={p} className="flex items-center gap-2 text-[14px]">
              <span className={`h-2.5 w-2.5 rounded-full ${PHASE_COLOR[i]}`} />
              <span className="font-semibold">{p}</span>
              <span className="text-ink-mute">{counts[i]} étape{counts[i] > 1 ? 's' : ''}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[13px] text-ink-mute">
          Les quatre phases suivent la progression d’une attaque, de la reconnaissance jusqu’à l’impact.
        </p>
      </div>

      {groups.map((g) => {
        const modes = scenarios.filter((s) => s.scenario_strategique_id === g)
        return (
          <section key={g}>
            <SectionTitle aside={`${modes.length} mode${modes.length > 1 ? 's' : ''} opératoire${modes.length > 1 ? 's' : ''}`}>
              Scénario stratégique <span className="mono text-crimson">{g}</span>
            </SectionTitle>
            <div className="space-y-4">
              {modes.map((s) => (
                <Mode key={s.id} s={s} />
              ))}
            </div>
          </section>
        )
      })}
      <p className="mt-6 text-[13px]">
        <Kicker>Lecture</Kicker>
        <span className="text-ink-mute"> Chaque étape cite une technique réelle du référentiel MITRE ATT&CK, cotée en probabilité de succès et difficulté ; la vraisemblance d’un mode est celle de son maillon le plus faible.</span>
      </p>
    </>
  )
}
