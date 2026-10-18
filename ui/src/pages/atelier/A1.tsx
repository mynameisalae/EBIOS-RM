/* eslint-disable @typescript-eslint/no-explicit-any */
import { SectionTitle } from '../../components/ui'
import { Grid, GravityPill, Tag } from './parts'

type O = Record<string, any>

export default function A1({ output }: { output: O }) {
  const biens: O[] = output.biens_essentiels ?? []
  const supports: O[] = output.biens_supports ?? []
  const events: O[] = output.evenements_redoutes ?? []
  const gaps: O[] = output.baseline_gaps_full ?? []
  const nameOf = (id?: string) => biens.find((b) => b.id === id)?.nom

  return (
    <>
      <SectionTitle aside={`${biens.length} identifiés`}>Ce qu’il faut protéger</SectionTitle>
      <Grid>
        {biens.map((b) => (
          <article key={b.id} className="card p-5">
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-[18px] font-extrabold leading-tight">{b.nom}</h3>
              <Tag>{b.nature}</Tag>
            </div>
            <p className="mt-2 text-[15px] text-ink-soft">{b.description}</p>
            <p className="mono mt-3 text-ink-mute">{b.id}</p>
          </article>
        ))}
      </Grid>

      <SectionTitle aside={`${events.length} événements`}>Ce que l’on redoute</SectionTitle>
      <div className="card divide-y divide-line">
        {events.map((e) => (
          <div key={e.id} className="flex flex-wrap items-center gap-x-5 gap-y-1 px-5 py-4">
            <span className="mono w-14 text-ink-mute">{e.id}</span>
            <p className="min-w-[260px] flex-1 text-[15px]">{e.description}</p>
            <span className="text-[13px] text-ink-mute">{nameOf(e.bien_essentiel_id)}</span>
            <GravityPill g={e.gravite} />
          </div>
        ))}
      </div>

      {supports.length > 0 && (
        <>
          <SectionTitle aside={`${supports.length} supports`}>Sur quoi cela repose</SectionTitle>
          <div className="flex flex-wrap gap-2">
            {supports.map((s) => (
              <span key={s.id} className="chip" title={s.description}>
                <span className="mono text-ink-mute">{s.id}</span> {s.nom}
              </span>
            ))}
          </div>
        </>
      )}

      {gaps.length > 0 && (
        <>
          <SectionTitle aside="Écart entre le socle de référence et l’existant">Où la sécurité est en retrait</SectionTitle>
          <div className="card divide-y divide-line">
            {gaps.map((g) => (
              <div key={g.gap_id} className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-4">
                <p className="min-w-[260px] flex-1 text-[15px]">{g.weakness}</p>
                <div className="flex flex-wrap gap-1.5">
                  {[...new Set<string>((g.controls ?? []).map((c: O) => c.framework))].map((f) => (
                    <Tag key={f}>{f}</Tag>
                  ))}
                </div>
                <span className="mono text-ink-mute">{g.gap_id}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  )
}
