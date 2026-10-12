import { Route, Routes } from 'react-router-dom'
import Shell from './components/Shell'
import Missions from './pages/Missions'
import Overview from './pages/Overview'
import Atelier from './pages/Atelier'
import Reports from './pages/Reports'
import Project from './pages/Project'

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Missions />} />
        <Route path="missions/:id" element={<Overview />} />
        <Route path="missions/:id/atelier/:n" element={<Atelier />} />
        <Route path="missions/:id/rapports" element={<Reports />} />
        <Route path="projet" element={<Project />} />
      </Route>
    </Routes>
  )
}
