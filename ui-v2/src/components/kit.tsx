import type { ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { levelIndex, vIndex } from '../lib/format'

const LEVEL_STYLE: Record<number, string> = {
  0: 'bg-line text-ink-soft',
  1: 'bg-lvl-1 text-ink',
  2: 'bg-lvl-2 text-ink',
  3: 'bg-lvl-3 text-white',
  4: 'bg-lvl-4 text-white',
}
const DOT_FILL: Record<number, string> = { 1: 'bg-lvl-1', 2: 'bg-lvl-2', 3: 'bg-lvl-3', 4: 'bg-lvl-4' }

export function LevelPill({ level, big = false }: { level?: string; big?: boolean }) {
  if (!level) return null
  const size = big ? 'px-5 py-2 text-[16px]' : 'px-3 py-0.5 text-[13px]'
  return <span className={`inline-block rounded-full font-bold ${size} ${LEVEL_STYLE[levelIndex(level)]}`}>{level}</span>
}

const GRAVITY = ['Minimale', 'Significative', 'Grave', 'Critique']
export function GravityPill({ g }: { g?: string }) {
  if (!g) return null
  const i = GRAVITY.indexOf(g) + 1
  return (
    <span className={`inline-block rounded-full px-3 py-0.5 text-[13px] font-bold ${LEVEL_STYLE[Math.min(i, 4)]}`} title="Gravité (Minimale < Significative < Grave < Critique)">
      {g}
    </span>
  )
}

/** Four dots, filled up to the level — V1..V4 read at a glance. */
export function VDots({ v, title }: { v?: string; title?: string }) {
  const n = vIndex(v)
  if (!n) return null
  return (
    <span className="inline-flex items-center gap-2" title={title ?? `Vraisemblance ${v} sur une échelle de V1 à V4`}>
      <span className="inline-flex gap-1">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={`h-2.5 w-2.5 rounded-full ${i <= n ? DOT_FILL[n] : 'bg-line'}`} />
        ))}
      </span>
      <span className="mono font-semibold text-ink-soft">{v}</span>
    </span>
  )
}

export function Tag({ children, tone = 'plain' }: { children: ReactNode; tone?: 'plain' | 'crimson' | 'gold' }) {
  const tones = {
    plain: 'bg-ground text-ink-soft',
    crimson: 'bg-crimson-tint text-crimson-deep',
    gold: 'bg-gold-tint text-gold-deep',
  }
  return <span className={`inline-flex items-center rounded-full px-3 py-0.5 text-[13px] font-semibold ${tones[tone]}`}>{children}</span>
}

export function Kicker({ children }: { children: ReactNode }) {
  return <p className="text-[12px] font-bold uppercase tracking-[0.14em] text-ink-mute">{children}</p>
}

/** The page's opening: where we are, what it is called, the question it answers. */
export function PageHead({ eyebrow, title, lead, size = 'md' }: { eyebrow?: ReactNode; title: ReactNode; lead?: ReactNode; size?: 'md' | 'xl' }) {
  return (
    <header className="rise pb-12 pt-16">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1 className={`mt-4 font-extrabold text-ink ${size === 'xl' ? 'text-[64px] leading-[1.02]' : 'text-[46px] leading-[1.06]'}`}>{title}</h1>
      {lead && <p className="mt-5 max-w-[60ch] text-[20px] leading-relaxed text-ink-soft">{lead}</p>}
    </header>
  )
}

/** One idea, said once, large — then the figures behind it. */
export function Takeaway({ children, figures }: { children: ReactNode; figures?: { label: string; value: number | string }[] }) {
  return (
    <section className="rise-2 sheet px-10 py-10">
      <Kicker>À retenir</Kicker>
      <p className="mt-3 max-w-[34ch] font-display text-[30px] font-bold leading-[1.2] text-ink [font-stretch:104%]">{children}</p>
      {figures && figures.length > 0 && (
        <dl className="mt-9 grid grid-cols-2 gap-x-10 gap-y-6 border-t border-line pt-8 sm:grid-cols-3">
          {figures.map((f) => (
            <div key={f.label}>
              <dd className="figure text-[48px]">{f.value}</dd>
              <dt className="mt-2 text-[15px] text-ink-mute">{f.label}</dt>
            </div>
          ))}
        </dl>
      )}
    </section>
  )
}

export function Section({ title, aside, children }: { title: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-24">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-1">
        <h2 className="text-[30px] font-extrabold leading-tight text-ink">{title}</h2>
        {aside && <p className="pb-1 text-[15px] text-ink-mute">{aside}</p>}
      </div>
      {children}
    </section>
  )
}

/** A row that says one line and opens to the rest — the cure for a wall of cards. */
export function Fold({
  lead,
  title,
  right,
  children,
  defaultOpen = false,
}: {
  lead?: ReactNode
  title: ReactNode
  right?: ReactNode
  children?: ReactNode
  defaultOpen?: boolean
}) {
  return (
    <details open={defaultOpen} className="group border-b border-line last:border-b-0">
      <summary className="flex cursor-pointer items-center gap-5 py-5 pr-1 transition-colors hover:text-crimson">
        {lead && <span className="mono w-16 flex-none font-bold text-crimson">{lead}</span>}
        <span className="min-w-0 flex-1 text-[19px] font-semibold leading-snug">{title}</span>
        {right && <span className="flex flex-none items-center gap-4">{right}</span>}
        <ChevronDown className="h-5 w-5 flex-none text-ink-mute transition-transform group-open:rotate-180" />
      </summary>
      {children && <div className="pb-8 pl-0 sm:pl-[84px]">{children}</div>}
    </details>
  )
}

export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`sheet px-8 py-2 ${className}`}>{children}</div>
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="sheet rise px-10 py-20 text-center">
      <p className="font-display text-[24px] font-bold text-ink">{title}</p>
      {children && <p className="mx-auto mt-3 max-w-[48ch] text-ink-soft">{children}</p>}
    </div>
  )
}

export function Failure({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-crimson-tint px-6 py-5 text-crimson-deep">
      <p className="font-semibold">Impossible de lire ces données</p>
      <p className="text-[15px]">{message}</p>
    </div>
  )
}

export function Loading() {
  return <p className="py-32 text-center text-ink-mute">Chargement…</p>
}
