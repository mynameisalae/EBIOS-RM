/* eslint-disable @typescript-eslint/no-explicit-any */
import { LevelPill, SectionTitle, VDots } from '../../components/ui'
import { Grid, GravityPill, Kicker, Tag } from './parts'

type O = Record<string, any>

export function A2({ output }: { output: O }) {
  const sources: O[] = output.sources_risque ?? []
  const objectifs: O[] = output.objectifs_vises ?? []
  const couples: O[] = output.couples ?? []
  const src = (id: string) => sources.find((s) => s.id === id)
  const obj = (id: string) => objectifs.find((o) => o.id === id)

  return (
    <>
      <SectionTitle aside={`${sources.length} retenues`}>Qui pourrait attaquer</SectionTitle>
      <Grid>
        {sources.map((s) => (
          <article key={s.id} className="card p-5">
            <Kicker>{s.categorie_libelle}</Kicker>
            <h3 className="mt-1 text-[18px] font-extrabold leading-tight">{s.nom}</h3>
            <p className="mt-2 text-[15px] text-ink-soft">{s.motivation || s.description}</p>
            <p className="mono mt-3 text-ink-mute">{s.id}</p>
          </article>
        ))}
      </Grid>

      <SectionTitle aside={`${couples.length} couples retenus`}>Ce qu’ils viseraient</SectionTitle>
      <div className="card divide-y divide-line">
        {couples.map((c) => (
          <div key={c.id} className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-4">
            <div className="min-w-[280px] flex-1">
              <p className="text-[15px] font-semibold">{src(c.source_risque_id)?.nom ?? c.source_risque_id}</p>
              <p className="text-[14px] text-ink-soft">→ {obj(c.objectif_vise_id)?.description ?? c.objectif_vise_id}</p>
            </div>
            <LevelPill level={c.pertinence} />
            <VDots v={c.vraisemblance_initiale} />
            <span className="mono text-ink-mute">{c.id}</span>
          </div>
        ))}
      </div>
    </>
  )
}

export function A3({ output }: { output: O }) {
  const scenarios: O[] = output.scenarios ?? []
  return (
    <>
      <SectionTitle aside={`${scenarios.length} scénarios`}>Les chemins d’ensemble</SectionTitle>
      <div className="space-y-4">
        {scenarios.map((s) => (
          <article key={s.id} className="card p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="mono font-semibold text-crimson">{s.id}</p>
              <div className="flex items-center gap-3">
                <GravityPill g={s.gravite} />
                <LevelPill level={s.pertinence} />
                <VDots v={s.vraisemblance_initiale} />
              </div>
            </div>
            <p className="mt-3 text-[17px] leading-snug">{s.resume}</p>
            {(s.parties_prenantes ?? []).length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Kicker>Écosystème</Kicker>
                {s.parties_prenantes.map((p: string) => (
                  <Tag key={p}>{p}</Tag>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </>
  )
}
