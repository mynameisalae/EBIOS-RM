import type { ReactNode } from 'react'
import { levelIndex, vIndex } from '../lib/format'
import type { AtelierState } from '../lib/api'

const LEVEL_STYLE: Record<number, string> = {
  0: 'bg-line text-ink-soft',
  1: 'bg-lvl-1 text-ink',
  2: 'bg-lvl-2 text-ink',
  3: 'bg-lvl-3 text-white',
  4: 'bg-lvl-4 text-white',
}
const DOT_FILL: Record<number, string> = { 1: 'bg-lvl-1', 2: 'bg-lvl-2', 3: 'bg-lvl-3', 4: 'bg-lvl-4' }

export function LevelPill({ level, size = 'md' }: { level?: string; size?: 'md' | 'lg' }) {
  if (!level) return null
  const big = size === 'lg' ? 'px-4 py-1.5 text-[15px]' : 'px-2.5 py-0.5 text-[12px]'
  return <span className={`inline-block rounded-full font-bold ${big} ${LEVEL_STYLE[levelIndex(level)]}`}>{level}</span>
}

/** Four dots, filled up to the level — V1..V4 read at a glance. */
export function VDots({ v, title }: { v?: string; title?: string }) {
  const n = vIndex(v)
  if (!n) return null
  return (
    <span className="inline-flex items-center gap-1.5" title={title ?? `Vraisemblance ${v} sur une échelle de V1 à V4`}>
      <span className="inline-flex gap-[3px]">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={`h-[9px] w-[9px] rounded-full ${i <= n ? DOT_FILL[n] : 'bg-line'}`} />
        ))}
      </span>
      <span className="mono font-semibold text-ink-soft">{v}</span>
    </span>
  )
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="eyebrow">{children}</p>
}

export function PageTitle({ eyebrow, title, lead }: { eyebrow?: string; title: ReactNode; lead?: ReactNode }) {
  return (
    <header className="rise mb-10">
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h1 className="mt-2 text-[40px] font-extrabold leading-[1.05] text-ink">{title}</h1>
      {lead && <p className="mt-3 max-w-[62ch] text-[17px] text-ink-soft">{lead}</p>}
    </header>
  )
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-4 mt-12 flex items-end justify-between gap-4 border-b border-line pb-2">
      <h2 className="text-[22px] font-extrabold text-ink">{children}</h2>
      {aside && <div className="pb-0.5 text-[13px] text-ink-mute">{aside}</div>}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card rise px-8 py-14 text-center">
      <p className="font-display text-[20px] font-bold text-ink">{title}</p>
      {children && <p className="mx-auto mt-2 max-w-[52ch] text-ink-soft">{children}</p>}
    </div>
  )
}

export function Failure({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-crimson/30 bg-crimson-tint px-5 py-4 text-crimson-deep">
      <p className="font-semibold">Impossible de lire ces données</p>
      <p className="text-[14px]">{message}</p>
    </div>
  )
}

export function Loading() {
  return <p className="py-16 text-center text-ink-mute">Chargement…</p>
}

const NODE: Record<AtelierState, string> = {
  approved: 'bg-crimson border-crimson',
  in_progress: 'bg-white border-crimson',
  absent: 'bg-white border-line-strong',
}

/** Five small linked nodes: how far a mission got along the chain of ateliers. */
export function MiniChain({ ateliers }: { ateliers: { n: number; state: AtelierState }[] }) {
  return (
    <span className="inline-flex items-center" aria-label="Avancement par atelier">
      {ateliers.map((a, i) => (
        <span key={a.n} className="inline-flex items-center">
          {i > 0 && <span className={`h-[2px] w-4 ${a.state === 'absent' ? 'bg-line' : 'bg-crimson/60'}`} />}
          <span className={`h-3 w-3 rounded-full border-2 ${NODE[a.state]}`} title={`Atelier ${a.n}`} />
        </span>
      ))}
    </span>
  )
}

export function StateDot({ state }: { state: AtelierState }) {
  return <span className={`inline-block h-2.5 w-2.5 rounded-full border-2 ${NODE[state]}`} />
}
