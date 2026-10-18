import { useParams } from 'react-router-dom'
import { api, useAsync } from '../lib/api'
import { Empty, Failure, Loading, PageHead, Takeaway } from '../components/kit'
import { PrevNext, Quality, Versions } from './atelier/parts'
import A1 from './atelier/A1'
import { A2, A3 } from './atelier/A2A3'
import A4 from './atelier/A4'
import A5 from './atelier/A5'

const LABELS = ['Cadrage et socle', 'Sources de risque', 'Scénarios stratégiques', 'Scénarios opérationnels', 'Traitement du risque']

export default function Atelier() {
  const { id = '', n = '1' } = useParams()
  const num = Number(n)
  const { data, error, loading } = useAsync(() => api.atelier(id, num), [id, num])
  if (loading) return <Loading />
  if (error || !data) return <Failure message={error} />

  const output = data.output
  const Body = { 1: A1, 2: A2, 3: A3, 4: A4, 5: A5 }[num as 1 | 2 | 3 | 4 | 5]

  return (
    <>
      <PageHead eyebrow={`Atelier ${num} sur 5 · ${data.organisation.nom ?? ''}`} title={data.label} lead={<span className="italic">{data.question}</span>} />
      {!output || !Body ? (
        <Empty title="Pas de résultats pour cet atelier">Cette base ne contient pas encore de version de l’atelier {num} pour cette mission.</Empty>
      ) : (
        <>
          <Takeaway figures={data.metrics}>{data.headline}</Takeaway>
          <Body output={output} />
          <Quality report={output.quality_report} />
        </>
      )}
      <Versions versions={data.versions} />
      <PrevNext id={id} n={num} labels={LABELS} />
    </>
  )
}
