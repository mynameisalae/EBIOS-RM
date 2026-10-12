/* eslint-disable @typescript-eslint/no-explicit-any */
import { ArrowRight } from 'lucide-react'
import { Fold, Kicker, LevelPill, Panel, Section, Tag, VDots } from '../../components/kit'

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

function Cost({ c }: { c?: string }) {
  const n = (c ?? '').length
  if (!n) return null
  return (
    <span className="inline-flex items-center gap-2" title={`Coût et complexité : ${c}`}>
      <span className="inline-flex gap-1">
        {[1, 2, 3].map((i) => (
          <span key={i} className={`h-2.5 w-2.5 rounded-full ${i <= n ? 'bg-ink-soft' : 'bg-line'}`} />
        ))}
      </span>
      coût
    </span>
  )
}

/** The heart of the atelier: where the risk stood, where it stands now. */
function Risk({ r, covered }: { r: O; covered: string[] }) {
  return (
    <article className="sheet px-10 py-9">
      <div className="flex flex-wrap items-center gap-3">
        <span className="mono font-bold text-crimson">{r.id}</span>
        <Tag>{String(r.option_traitement ?? '').replace(/^./, (c: string) => c.toUpperCase())}</Tag>
        {r.accepte_par && <Tag tone="gold">Accepté par {r.accepte_par}</Tag>}
      </div>
      <p className="mt-4 max-w-[58ch] font-display text-[24px] font-bold leading-snug [font-stretch:104%]">{r.libelle}</p>

      <div className="mt-9 flex flex-wrap items-center gap-x-10 gap-y-6">
        <div>
          <Kicker>Avant traitement</Kicker>
          <div className="mt-3 flex items-center gap-4">
            <LevelPill level={r.niveau_risque} big />
            <VDots v={r.vraisemblance} />
          </div>
        </div>
        <ArrowRight className="h-7 w-7 text-ink-mute" />
        <div>
          <Kicker>Après traitement</Kicker>
          <div className="mt-3 flex items-center gap-4">
            <LevelPill level={r.niveau_risque_residuel} big />
            <VDots v={r.vraisemblance_residuelle} />
          </div>
        </div>
        <div className="ml-auto text-right">
          <p className="figure text-[44px]">{(r.mesures_ids ?? []).length}</p>
          <p className="text-[14px] text-ink-mute">mesures mobilisées</p>
        </div>
      </div>

      {r.motif_residuel && <p className="mt-8 max-w-[64ch] border-t border-line pt-6 text-[17px] text-ink-soft">{r.motif_residuel}</p>}
      {covered.length > 0 && (
        <p className="mt-4 flex flex-wrap items-center gap-2 text-[15px] text-ink-mute">
          Événements redoutés couverts :
          {covered.map((id) => (
            <span key={id} className="mono rounded-full bg-ground px-2.5 py-0.5">
              {id}
            </span>
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
      <Section title="Du risque au risque résiduel" aside="Chaque risque est ramené à un niveau résiduel, accepté par la direction">
        <div className="space-y-6">
          {risks.map((r) => (
            <Risk key={r.id} r={r} covered={coverage.filter((c) => (c.risques_ids ?? []).includes(r.id)).map((c) => c.evenement_redoute_id)} />
          ))}
        </div>
      </Section>

      <Section title="Le plan de traitement" aside={`${measures.length} mesures distinctes`}>
        <div className="space-y-10">
          {AXES.map((axe) => {
            const items = measures.filter((m) => norm(m.axe) === axe.key)
            if (items.length === 0) return null
            return (
              <div key={axe.key}>
                <div className="mb-3 flex flex-wrap items-baseline gap-x-4">
                  <h3 className="text-[22px] font-extrabold">{axe.label}</h3>
                  <span className="text-[15px] text-ink-mute">{axe.hint}</span>
                </div>
                <Panel>
                  {items.map((m, i) => (
                    <Fold key={`${m.id}-${i}`} lead={m.id} title={m.libelle} right={m.priorite ? <Tag tone={m.priorite === 'P1' ? 'crimson' : m.priorite === 'P2' ? 'gold' : 'plain'}>{m.priorite}</Tag> : undefined}>
                      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[15px] text-ink-mute">
                        <Cost c={m.cout_complexite} />
                        {m.echeance && <span>Échéance : {m.echeance}</span>}
                        {m.aliases.length > 0 && <span>Même mesure que {m.aliases.join(', ')}</span>}
                      </div>
                      {(m.mitigation_ids_attck ?? []).length > 0 && (
                        <p className="mt-3 flex flex-wrap items-center gap-2 text-[15px] text-ink-mute">
                          Mitigations MITRE ATT&CK :
                          {m.mitigation_ids_attck.map((a: string) => (
                            <span key={a} className="mono rounded-full bg-ground px-2.5 py-0.5">
                              {a}
                            </span>
                          ))}
                        </p>
                      )}
                    </Fold>
                  ))}
                </Panel>
              </div>
            )
          })}
        </div>
      </Section>

      {(follow.comite || indicators.length > 0) && (
        <Section title="Le cadre de suivi" aside="Comment le plan reste piloté dans la durée">
          {follow.comite && <p className="mb-6 max-w-[62ch] text-[18px] text-ink-soft">{follow.comite}</p>}
          <Panel>
            {indicators.map((ind) => (
              <Fold key={ind.id} lead={ind.id} title={ind.libelle} right={<Tag>{ind.cible}</Tag>}>
                <p className="text-[16px] capitalize text-ink-mute">Fréquence : {ind.frequence}</p>
              </Fold>
            ))}
          </Panel>
        </Section>
      )}
    </>
  )
}
