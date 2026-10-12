/* eslint-disable @typescript-eslint/no-explicit-any */
import { Fold, GravityPill, Kicker, LevelPill, Panel, Section, Tag, VDots } from '../../components/kit'

type O = Record<string, any>

export function A2({ output }: { output: O }) {
  const sources: O[] = output.sources_risque ?? []
  const objectifs: O[] = output.objectifs_vises ?? []
  const couples: O[] = output.couples ?? []
  const src = (id: string) => sources.find((s) => s.id === id)
  const obj = (id: string) => objectifs.find((o) => o.id === id)

  return (
    <>
      <Section title="Qui pourrait attaquer" aside={`${sources.length} sources retenues`}>
        <Panel>
          {sources.map((s) => (
            <Fold key={s.id} lead={s.id} title={s.nom} right={<Tag>{s.categorie_libelle}</Tag>}>
              <p className="max-w-[62ch] text-ink-soft">{s.motivation || s.description}</p>
            </Fold>
          ))}
        </Panel>
      </Section>

      <Section title="Ce qu’ils viseraient" aside={`${couples.length} couples retenus`}>
        <Panel>
          {couples.map((c) => (
            <Fold
              key={c.id}
              lead={c.id}
              title={src(c.source_risque_id)?.nom ?? c.source_risque_id}
              right={
                <>
                  <LevelPill level={c.pertinence} />
                  <span className="hidden sm:inline">
                    <VDots v={c.vraisemblance_initiale} />
                  </span>
                </>
              }
            >
              <Kicker>Objectif visé</Kicker>
              <p className="mt-1 max-w-[62ch] text-ink-soft">{obj(c.objectif_vise_id)?.description ?? c.objectif_vise_id}</p>
            </Fold>
          ))}
        </Panel>
      </Section>
    </>
  )
}

export function A3({ output }: { output: O }) {
  const scenarios: O[] = output.scenarios ?? []
  return (
    <Section title="Les chemins d’ensemble" aside={`${scenarios.length} scénarios stratégiques`}>
      <Panel>
        {scenarios.map((s) => (
          <Fold
            key={s.id}
            lead={s.id}
            title={s.resume}
            right={
              <>
                <GravityPill g={s.gravite} />
                <span className="hidden sm:inline">
                  <VDots v={s.vraisemblance_initiale} />
                </span>
              </>
            }
          >
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <LevelPill level={s.pertinence} />
              <span className="text-[15px] text-ink-mute">pertinence du scénario</span>
            </div>
            {(s.parties_prenantes ?? []).length > 0 && (
              <div className="mt-5">
                <Kicker>Écosystème concerné</Kicker>
                <div className="mt-2 flex flex-wrap gap-2">
                  {s.parties_prenantes.map((p: string) => (
                    <Tag key={p}>{p}</Tag>
                  ))}
                </div>
              </div>
            )}
          </Fold>
        ))}
      </Panel>
    </Section>
  )
}
