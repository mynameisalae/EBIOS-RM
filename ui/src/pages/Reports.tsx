import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { Download, Loader2, Upload, X } from 'lucide-react'
import { api, useAsync, type Job } from '../lib/api'
import { Failure, Loading, PageTitle, SectionTitle } from '../components/ui'

/** A small portrait page, like the cover of the real document. */
function Sheet({ title, accent }: { title: string; accent: string }) {
  return (
    <div className="relative flex aspect-[3/4] w-[132px] flex-none flex-col rounded-md border border-line bg-white p-3 shadow-sheet">
      <img src="/ogsbc-logo.png" alt="" className="h-5 w-auto self-start" />
      <p className="mt-6 font-display text-[13px] font-extrabold uppercase leading-tight text-ink">{title}</p>
      <span className="mt-2 h-[3px] w-8" style={{ background: accent }} />
      <div className="mt-auto space-y-1.5">
        {[88, 100, 72, 94, 60].map((w, i) => (
          <span key={i} className="block h-[3px] rounded bg-line" style={{ width: `${w}%` }} />
        ))}
      </div>
    </div>
  )
}

function Step({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full border-2 border-crimson font-display text-[13px] font-extrabold text-crimson">{n}</span>
      <p className="pt-0.5 text-[15px] text-ink-soft">{children}</p>
    </li>
  )
}

export default function Reports() {
  const { id = '' } = useParams()
  const { data, error, loading } = useAsync(() => api.mission(id), [id])
  const [annex, setAnnex] = useState<File | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [jobId, setJobId] = useState('')
  const [failure, setFailure] = useState('')
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!jobId || job?.status === 'done' || job?.status === 'error') return
    const timer = setInterval(() => api.job(jobId).then(setJob, (e: Error) => setFailure(e.message)), 1500)
    return () => clearInterval(timer)
  }, [jobId, job?.status])

  if (loading) return <Loading />
  if (error || !data) return <Failure message={error} />

  const running = job?.status === 'running' || (jobId !== '' && job === null)
  const start = async () => {
    setFailure('')
    setJob(null)
    try {
      const started = await api.startReport(id, annex ?? undefined)
      setJobId(started.job_id)
    } catch (e) {
      setFailure((e as Error).message)
    }
  }

  return (
    <>
      <PageTitle
        eyebrow={`Mission · ${data.organisation.nom ?? data.mission.name}`}
        title="Les rapports"
        lead="Deux documents, deux logiques : l’annexe garde la trace de ce que l’auditeur a fait ; le rapport raconte l’étude à l’organisation. Tous deux reprennent la mise en page de nos rapports."
      />

      <SectionTitle>Le parcours</SectionTitle>
      <ol className="rise grid gap-5 md:grid-cols-3">
        <Step n={1}>L’agent produit l’<b>annexe d’audit</b> : versions, décisions, provenance, événements anormaux.</Step>
        <Step n={2}>L’auditeur la complète dans Word : une case <b>« Appréciation »</b> par événement anormal.</Step>
        <Step n={3}>On joint l’annexe remplie et l’agent rédige le <b>rapport de mission</b>, appréciations comprises.</Step>
      </ol>

      <div className="mt-10 grid gap-5 lg:grid-cols-2">
        <section className="card rise flex gap-6 p-6">
          <Sheet title="Annexe d’audit" accent="#C8960C" />
          <div className="flex flex-1 flex-col">
            <p className="eyebrow">Pour l’auditeur · sans IA</p>
            <h2 className="mt-1 text-[24px] font-extrabold leading-tight">Annexe d’audit</h2>
            <p className="mt-2 text-[15px] text-ink-soft">
              Pur rendu des données de la mission : chaque valeur est lue telle quelle, rien n’est rédigé par un modèle.
            </p>
            <a className="btn-quiet mt-auto self-start" href={api.annexUrl(id)} download>
              <Download className="h-4 w-4" /> Télécharger l’annexe (.docx)
            </a>
          </div>
        </section>

        <section className="card rise flex gap-6 p-6">
          <Sheet title="Rapport de mission" accent="#BE1E2D" />
          <div className="flex flex-1 flex-col">
            <p className="eyebrow">Pour l’organisation · rédigé par l’IA</p>
            <h2 className="mt-1 text-[24px] font-extrabold leading-tight">Rapport de mission</h2>
            <p className="mt-2 text-[15px] text-ink-soft">
              Chaque phrase renvoie aux champs qui la fondent, et un contrôle automatique la vérifie avant qu’elle soit retenue.
            </p>

            {data.can_write_report ? (
              <div className="mt-4">
                <input ref={input} type="file" accept=".docx" className="hidden" onChange={(e) => setAnnex(e.target.files?.[0] ?? null)} />
                {annex ? (
                  <p className="flex items-center gap-2 text-[14px] text-ink-soft">
                    <span className="truncate font-semibold">{annex.name}</span>
                    <button onClick={() => { setAnnex(null); if (input.current) input.current.value = '' }} aria-label="Retirer l’annexe" className="text-ink-mute hover:text-crimson">
                      <X className="h-4 w-4" />
                    </button>
                  </p>
                ) : (
                  <button onClick={() => input.current?.click()} className="inline-flex items-center gap-2 text-[14px] font-semibold text-ink-soft hover:text-crimson">
                    <Upload className="h-4 w-4" /> Joindre l’annexe remplie (facultatif)
                  </button>
                )}
                <button onClick={start} disabled={running} className="btn-primary mt-4 disabled:opacity-60">
                  {running ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {running ? 'Rédaction en cours…' : job?.status === 'done' ? 'Rédiger à nouveau' : 'Rédiger le rapport'}
                </button>
              </div>
            ) : (
              <p className="mt-4 text-[14px] text-ink-mute">Aucun atelier n’est encore approuvé : il n’y a rien à rapporter.</p>
            )}
          </div>
        </section>
      </div>

      {failure && <div className="mt-6"><Failure message={failure} /></div>}

      {job && (
        <section className="card rise mt-6 p-6">
          {job.status === 'running' && (
            <>
              <p className="font-display text-[18px] font-extrabold">Rédaction en cours</p>
              <p className="text-[14px] text-ink-mute">Une section à la fois — comptez une à deux minutes.</p>
              <ul className="mono mt-4 space-y-1 text-ink-soft">
                {job.lines.slice(-6).map((l, i) => <li key={i}>{l}</li>)}
              </ul>
            </>
          )}
          {job.status === 'error' && <Failure message={job.error} />}
          {job.status === 'done' && job.summary && (
            <>
              <p className="font-display text-[20px] font-extrabold">Le rapport est prêt</p>
              <p className="mt-1 text-[15px] text-ink-soft">
                {job.summary.sections} section{job.summary.sections > 1 ? 's' : ''}, {job.summary.statements} affirmation{job.summary.statements > 1 ? 's' : ''} retenue{job.summary.statements > 1 ? 's' : ''}
                {job.summary.corrected > 0 ? ` (dont ${job.summary.corrected} corrigée${job.summary.corrected > 1 ? 's' : ''} après vérification)` : ''}.
              </p>
              {job.summary.skipped.length > 0 && (
                <p className="mt-2 text-[14px] text-ink-mute">
                  Non incluses : {job.summary.skipped.map((s) => `${s.title} (${s.reason})`).join(' ; ')}.
                </p>
              )}
              {job.summary.rejected.length > 0 && (
                <details className="mt-3 text-[14px]">
                  <summary className="cursor-pointer font-semibold text-ink-soft">
                    {job.summary.rejected.length} affirmation{job.summary.rejected.length > 1 ? 's' : ''} écartée{job.summary.rejected.length > 1 ? 's' : ''} par le contrôle
                  </summary>
                  <ul className="mt-2 space-y-2 text-ink-soft">
                    {job.summary.rejected.map((r, i) => (
                      <li key={i}>« {r.text} » — <span className="text-ink-mute">{r.reason}</span></li>
                    ))}
                  </ul>
                </details>
              )}
              <a className="btn-primary mt-5" href={api.jobFileUrl(job.id)} download>
                <Download className="h-4 w-4" /> Télécharger le rapport (.docx)
              </a>
            </>
          )}
        </section>
      )}
    </>
  )
}
