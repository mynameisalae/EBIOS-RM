import { Link, NavLink, Outlet, useMatch } from 'react-router-dom'
import { api, useAsync, type AtelierState } from '../lib/api'

const top = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-4 py-2 text-[15px] font-semibold transition-colors ${isActive ? 'bg-ink text-white' : 'text-ink-soft hover:text-ink'}`

function Dot({ n, state, active }: { n: number; state: AtelierState; active: boolean }) {
  const fill =
    state === 'approved' ? 'bg-crimson text-white border-crimson' : state === 'in_progress' ? 'bg-white text-crimson border-crimson' : 'bg-white text-ink-mute border-line-strong'
  return (
    <span className={`flex h-8 w-8 items-center justify-center rounded-full border-2 font-display text-[13px] font-extrabold ${fill} ${active ? 'ring-4 ring-crimson/15' : ''}`}>{n}</span>
  )
}

/** The chain of five ateliers, always at hand: where the mission is, and a way to any step. */
function MissionBar({ id }: { id: string }) {
  const { data } = useAsync(() => api.mission(id), [id])
  const onAtelier = useMatch('/missions/:id/atelier/:n')
  if (!data) return <div className="h-[72px] border-b border-line bg-sheet" />
  const current = onAtelier ? Number(onAtelier.params.n) : 0
  return (
    <div className="sticky top-[72px] z-20 border-b border-line bg-sheet/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1080px] items-center gap-6 px-6 lg:px-10">
        <NavLink end to={`/missions/${id}`} className="hidden whitespace-nowrap py-4 font-display text-[16px] font-extrabold text-ink [font-stretch:108%] hover:text-crimson sm:block">
          {data.organisation.nom || data.mission.name}
        </NavLink>
        <nav className="flex flex-1 items-center gap-1 py-3" aria-label="Ateliers">
          {data.ateliers.map((a, i) => (
            <div key={a.n} className="flex items-center">
              {i > 0 && <span className={`mx-1 h-[2px] w-4 sm:w-8 ${a.state === 'absent' ? 'bg-line' : 'bg-crimson/50'}`} />}
              <NavLink to={`/missions/${id}/atelier/${a.n}`} className="flex items-center gap-2.5 rounded-full py-1 pl-1 pr-3 hover:bg-ground" title={a.label}>
                <Dot n={a.n} state={a.state} active={current === a.n} />
                {current === a.n && <span className="hidden whitespace-nowrap text-[14px] font-semibold text-ink lg:inline">{a.label}</span>}
              </NavLink>
            </div>
          ))}
        </nav>
        <NavLink to={`/missions/${id}/rapports`} className={top}>
          Rapports
        </NavLink>
      </div>
    </div>
  )
}

export default function Shell() {
  const match = useMatch('/missions/:id/*')
  const id = match?.params.id
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-sheet">
        <div className="mx-auto flex h-[72px] max-w-[1080px] items-center gap-8 px-6 lg:px-10">
          <Link to="/" aria-label="Accueil">
            <img src="/ogsbc-logo.png" alt="OGSBC — Security Business Consulting" className="h-10 w-auto" />
          </Link>
          <span className="hidden h-6 w-px bg-line-strong sm:block" />
          <p className="eyebrow hidden sm:block">Agent EBIOS RM</p>
          <nav className="ml-auto flex items-center gap-1">
            <NavLink end to="/" className={top}>
              Missions
            </NavLink>
            <NavLink to="/projet" className={top}>
              Le projet
            </NavLink>
          </nav>
        </div>
      </header>
      {id && <MissionBar id={id} />}
      <main className="mx-auto w-full max-w-[1080px] flex-1 px-6 pb-32 lg:px-10">
        <Outlet />
      </main>
      <footer className="border-t border-line bg-sheet">
        <div className="mx-auto flex max-w-[1080px] flex-wrap items-center justify-between gap-3 px-6 py-8 text-[14px] text-ink-mute lg:px-10">
          <span>OGSBC · Security Business Consulting</span>
          <span>L’IA propose · le code vérifie · l’auditeur décide</span>
        </div>
      </footer>
    </div>
  )
}
