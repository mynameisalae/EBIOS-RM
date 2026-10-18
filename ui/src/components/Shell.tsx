import { NavLink, Outlet, useMatch } from 'react-router-dom'
import { api, useAsync } from '../lib/api'
import { StateDot } from './ui'

const linkBase = 'flex items-center gap-3 rounded-lg px-3 py-2 text-[15px] font-semibold transition-colors'
const link = ({ isActive }: { isActive: boolean }) =>
  `${linkBase} ${isActive ? 'bg-crimson-tint text-crimson' : 'text-ink-soft hover:bg-paper hover:text-ink'}`

function MissionNav({ id }: { id: string }) {
  const { data } = useAsync(() => api.mission(id), [id])
  if (!data) return null
  return (
    <div className="mt-8">
      <p className="eyebrow px-3">Mission</p>
      <p className="mt-1 px-3 font-display text-[17px] font-extrabold leading-tight text-ink">
        {data.organisation.nom || data.mission.name}
      </p>
      <p className="mono mt-0.5 px-3 text-ink-mute">{data.mission.id.slice(0, 8)}</p>
      <nav className="mt-4 space-y-0.5">
        <NavLink end to={`/missions/${id}`} className={link}>
          Vue d’ensemble
        </NavLink>
        {data.ateliers.map((a) => (
          <NavLink key={a.n} to={`/missions/${id}/atelier/${a.n}`} className={link}>
            <StateDot state={a.state} />
            <span className="flex-1">{a.label}</span>
            <span className="mono text-ink-mute">A{a.n}</span>
          </NavLink>
        ))}
        <NavLink to={`/missions/${id}/rapports`} className={(s) => `${link(s)} !mt-3 border-t border-line !rounded-none !pt-4`}>
          Rapports
        </NavLink>
      </nav>
    </div>
  )
}

export default function Shell() {
  const match = useMatch('/missions/:id/*')
  const id = match?.params.id
  return (
    <div className="min-h-screen">
      <aside className="border-b border-line bg-white px-5 py-6 lg:fixed lg:inset-y-0 lg:left-0 lg:w-[256px] lg:overflow-y-auto lg:border-b-0 lg:border-r">
        <img src="/ogsbc-logo.png" alt="OGSBC — Security Business Consulting" className="h-11 w-auto" />
        <p className="eyebrow mt-4 px-1">Agent EBIOS RM</p>
        <nav className="mt-4 space-y-0.5">
          <NavLink end to="/" className={link}>
            Missions
          </NavLink>
          <NavLink to="/projet" className={link}>
            Le projet
          </NavLink>
        </nav>
        {id && <MissionNav id={id} />}
      </aside>
      <main className="lg:ml-[256px]">
        <div className="mx-auto max-w-[1120px] px-6 py-12 lg:px-14">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
