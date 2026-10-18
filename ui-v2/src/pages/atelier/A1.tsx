/* eslint-disable @typescript-eslint/no-explicit-any */
import { Fold, GravityPill, Panel, Section, Tag } from '../../components/kit'

type O = Record<string, any>

export default function A1({ output }: { output: O }) {
  const biens: O[] = output.biens_essentiels ?? []
  const supports: O[] = output.biens_supports ?? []
  const events: O[] = output.evenements_redoutes ?? []
  const gaps: O[] = output.baseline_gaps_full ?? []
  const nameOf = (id?: string) => biens.find((b) => b.id === id)?.nom

  return (
    <>
      <Section title="Ce qu’il faut protéger" aside={`${biens.length} biens essentiels`}>
        <Panel>
          {biens.map((b) => (
            <Fold key={b.id} lead={b.id} title={b.nom} right={<Tag>{b.nature}</Tag>}>
              <p className="max-w-[62ch] text-ink-soft">{b.description}</p>
            </Fold>
          ))}
        </Panel>
      </Section>

      <Section title="Ce que l’on redoute" aside={`${events.length} événements redoutés`}>
        <Panel>
          {events.map((e) => (
            <Fold key={e.id} lead={e.id} title={e.description} right={<GravityPill g={e.gravite} />}>
              {nameOf(e.bien_essentiel_id) && <p className="text-[16px] text-ink-mute">Atteint : {nameOf(e.bien_essentiel_id)}</p>}
            </Fold>
          ))}
        </Panel>
      </Section>

      {supports.length > 0 && (
        <Section title="Sur quoi cela repose" aside={`${supports.length} supports`}>
          <Panel>
            {supports.map((s) => (
              <Fold key={s.id} lead={s.id} title={s.nom}>
                <p className="max-w-[62ch] text-ink-soft">{s.description}</p>
              </Fold>
            ))}
          </Panel>
        </Section>
      )}

      {gaps.length > 0 && (
        <Section title="Où la sécurité est en retrait" aside="Écart entre le socle de référence et l’existant">
          <Panel>
            {gaps.map((g) => (
              <Fold
                key={g.gap_id}
                lead={g.gap_id}
                title={g.weakness}
                right={
                  <span className="hidden gap-2 sm:flex">
                    {[...new Set<string>((g.controls ?? []).map((c: O) => c.framework))].slice(0, 3).map((f) => (
                      <Tag key={f}>{f}</Tag>
                    ))}
                  </span>
                }
              >
                <p className="text-[16px] text-ink-mute">{(g.controls ?? []).length} contrôle(s) de référentiel concerné(s).</p>
              </Fold>
            ))}
          </Panel>
        </Section>
      )}
    </>
  )
}
