/* eslint-disable @typescript-eslint/no-explicit-any */
import { ArrowRight } from 'lucide-react'
import { LevelPill, SectionTitle, VDots } from '../../components/ui'
import { Kicker, Tag } from './parts'

type O = Record<string, any>

const AXES: { key: string; label: string; hint: string }[] = [
  { key: 'gouvernance', label: 'Gouvernance', hint: 'organisation, rôles, pilotage' },
  { key: 'protection', label: 'Protection', hint: 'empêcher l’attaque d’aboutir' },
  { key: 'defense', label: 'Défense', hint: 'détecter et réagir' },
  { key: 'resilience', label: 'Résilience', hint: 'continuer malgré l’incident' },
]
const norm = (s?: string) => (s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** Exact same wording under two ids is one measure: shown once, with its other ids. */
function distinctMeasures(measures: O[]): (O & { aliases: string[] })[] {
  const byLabel = new Map<string, O & { aliases: string[] }>()
  for (const m of measures) {
    const key = norm(m.libelle) || m.id
    const seen = byLabel.get(key)
    if (!seen) byLabel.set(key, { ...m, aliases: [] })
    else if (m.id !== seen.id && !seen.aliases.includes(m.id)) seen.aliases.push(m.id)
  }
  return [...byLabel.values()]
}

function Priority({ p }: { p?: string }) {
  if (!p) return null
  return <Tag tone={p === 'P1' ? 'crimson' : p === 'P2' ? 'gold' : 'plain'}>{p}</Tag>
}

function Cost({ c }: { c?: string }) {
  const n = (c ?? '').length
  if (!n) return null
  return (
    <span className="inline-flex gap-[3px]" title={`Coût et complexité : ${c}`}>
      {[1, 2, 3].map((i) => (
        <span key={i} className={`h-2 w-2 rounded-full ${i <= n ? 'bg-ink-soft' : 'bg-line'}`} />
      ))}
    </span>
  )
}

function Risk({ r, covered }: { r: O; covered: string[] }) {
  return (
    <article className="card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="mono font-bold text-crimson">{r.id}</p>
        <div className="flex flex-wrap gap-2">
          <Tag>{String(r.option_traitement ?? '').replace(/^./, (c: string) => c.toUpperCase())}</Tag>
          {r.accepte_par && <Tag tone="gold">Accepté par {r.accepte_par}</Tag>}
        </div>
      </div>
      <p className="mt-2 max-w-[78ch] text-[16px] leading-snug">{r.libelle}</p>

      <div className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-5">
        <div>
          <Kicker>Avant traitement</Kicker>
          <div className="mt-2 flex items-center gap-4">
            <LevelPill level={r.niveau_risque} size="lg" />
            <VDots v={r.vraisemblance} />
          </div>
        </div>
        <ArrowRight className="h-6 w-6 text-ink-mute" />
        <div>
          <Kicker>Après traitement</Kicker>
          <div className="mt-2 flex items-center gap-4">
            <LevelPill level={r.niveau_risque_residuel} size="lg" />
            <VDots v={r.vraisemblance_residuelle} />
          </div>
        </div>
        <div className="ml-auto text-right">
          <p className="font-display text-[28px] font-extrabold leading-none">{(r.mesures_ids ?? []).length}</p>
          <p className="text-[13px] text-ink-mute">mesures mobilisées</p>
        </div>
      </div>

      {r.motif_residuel && <p className="mt-5 border-t border-line pt-4 text-[14px] leading-relaxed text-ink-soft">{r.motif_residuel}</p>}
      {covered.length > 0 && (
        <p className="mt-3 flex flex-wrap items-center gap-2 text-[13px] text-ink-mute">
          Événements redoutés couverts :
          {covered.map((id) => (
            <span key={id} className="mono rounded border border-line px-1.5">{id}</span>
          ))}
        </p>
      )}
    </article>
  )
}

export default function A5({ output }: { output: O }) {
  const risks: O[] = output.risques ?? []
  const measures = distinctMeasures(output.mesures ?? [])
  const coverage: O[] = output.couverture_er ?? []
  const follow: O = output.cadre_suivi ?? {}
  const indicators: O[] = follow.indicateurs ?? []

  return (
    <>
      <SectionTitle aside="Chaque risque est ramené à un niveau résiduel, accepté par la direction">Du risque au risque résiduel</SectionTitle>
      <div className="space-y-4">
        {risks.map((r) => (
          <Risk key={r.id} r={r} covered={coverage.filter((c) => (c.risques_ids ?? []).includes(r.id)).map((c) => c.evenement_redoute_id)} />
        ))}
      </div>

      <SectionTitle aside={`${measures.length} mesures distinctes`}>Le plan de traitement</SectionTitle>
      <div className="grid gap-5 md:grid-cols-2">
        {AXES.map((axe) => {
          const items = measures.filter((m) => norm(m.axe) === axe.key)
          if (items.length === 0) return null
          return (
            <section key={axe.key} className="card p-5">
              <div className="mb-3 flex items-baseline justify-between">
                <h3 className="text-[18px] font-extrabold">{axe.label}</h3>
                <span className="text-[12px] text-ink-mute">{axe.hint}</span>
              </div>
              <ul className="divide-y divide-line">
                {items.map((m, i) => (
                  <li key={`${m.id}-${i}`} className="py-3">
                    <div className="flex items-start gap-3">
                      <span className="mono mt-0.5 w-11 flex-none font-bold text-ink-soft">{m.id}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[15px] font-semibold leading-snug">{m.libelle}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[12px] text-ink-mute">
                          <Priority p={m.priorite} />
                          <Cost c={m.cout_complexite} />
                          {m.echeance && <span>{m.echeance}</span>}
                          {(m.mitigation_ids_attck ?? []).map((a: string) => (
                            <span key={a} className="mono rounded border border-line px-1.5" title="Mitigation MITRE ATT&CK">{a}</span>
                          ))}
                          {m.aliases.length > 0 && <span>aussi {m.aliases.join(', ')}</span>}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>

      {(follow.comite || indicators.length > 0) && (
        <>
          <SectionTitle aside="Comment le plan reste piloté dans la durée">Le cadre de suivi</SectionTitle>
          {follow.comite && <p className="mb-4 max-w-[80ch] text-[15px] text-ink-soft">{follow.comite}</p>}
          <div className="card divide-y divide-line">
            {indicators.map((ind) => (
              <div key={ind.id} className="flex flex-wrap items-center gap-x-5 gap-y-1 px-5 py-3.5">
                <span className="mono w-14 text-ink-mute">{ind.id}</span>
                <p className="min-w-[240px] flex-1 text-[15px]">{ind.libelle}</p>
                <Tag>{ind.cible}</Tag>
                <span className="w-28 text-right text-[13px] capitalize text-ink-mute">{ind.frequence}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  )
}
