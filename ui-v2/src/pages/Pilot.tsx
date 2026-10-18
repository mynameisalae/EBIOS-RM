import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowRight, Check, Download, Loader2, Square } from 'lucide-react'
import { api, useAsync, type PilotPrompt, type PilotState } from '../lib/api'
import { Failure, Kicker, Loading, PageHead } from '../components/kit'

type Line = { text: string; kind: 'title' | 'answer' | 'plain' | 'gap' }

/** The terminal's output, read as a page: headings, the auditor's own answers, the rest as prose. */
function toLine(raw: string): Line {
  if (!raw.trim()) return { text: '', kind: 'gap' }
  const title = /^=+\s*(.*?)\s*=*$/.exec(raw.trim())
  if (raw.trim().startsWith('===') && title) return { text: title[1], kind: 'title' }
  if (raw.startsWith('> ')) return { text: raw.slice(2), kind: 'answer' }
  return { text: raw.replace(/\s*={3,}\s*$/, ''), kind: 'plain' }   // a heading whose closing === landed on the next line
}

const OPTION_LINE = /^\s+\[[^\]]+\]\s+\S/

function Journal({ lines, choicePending }: { lines: string[]; choicePending: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    box.current?.scrollTo({ top: box.current.scrollHeight })
  }, [lines.length])
  let shown = lines
  if (choicePending) {                      // the menu above the buttons would say everything twice
    let end = shown.length
    while (end > 0 && OPTION_LINE.test(shown[end - 1])) end--
    shown = shown.slice(0, end)
  }
  const parsed = shown.map(toLine).filter((l, i, all) => !(l.kind === 'gap' && (i === 0 || all[i - 1].kind === 'gap')))
  return (
    <div ref={box} className="max-h-[52vh] min-h-[160px] overflow-y-auto rounded-2xl bg-sheet px-8 py-7 shadow-soft" aria-live="polite">
      {parsed.length === 0 && <p className="text-ink-mute">Le journal de la mission s’affichera ici.</p>}
      {parsed.map((l, i) =>
        l.kind === 'gap' ? (
          <div key={i} className="h-3" />
        ) : l.kind === 'title' ? (
          <p key={i} className="mb-1 mt-6 font-display text-[19px] font-extrabold text-ink first:mt-0">{l.text}</p>
        ) : l.kind === 'answer' ? (
          <p key={i} className="my-2 ml-auto w-fit max-w-[85%] rounded-2xl bg-crimson-tint px-4 py-2 text-[16px] text-crimson-deep">{l.text}</p>
        ) : (
          <p key={i} className="whitespace-pre-wrap text-[16px] leading-relaxed text-ink-soft">{l.text}</p>
        ),
      )}
    </div>
  )
}

function PromptCard({ prompt, missionId, lines, onAnswer }: { prompt: PilotPrompt; missionId: string; lines: string[]; onAnswer: (text: string) => void }) {
  const [text, setText] = useState('')
  useEffect(() => setText(''), [prompt.id])
  const approval = prompt.text.includes('Approuvez-vous')
  const gate = approval ? [...lines].reverse().map((l) => /Validation de Atelier (\d)/.exec(l)).find(Boolean) : null
  const question = prompt.text.replace(/[>:\s]+$/, '').replace(/\[\s*oui\s*\/\s*non\s*\]/i, '').trim()

  return (
    <section className="sheet rise mt-6 px-8 py-8 ring-2 ring-crimson/20">
      <Kicker>{approval ? 'À vous de décider' : 'L’agent attend votre réponse'}</Kicker>
      {question && <p className="mt-2 max-w-[60ch] text-[20px] font-semibold leading-snug">{question}</p>}

      {gate && (
        <a className="mt-3 inline-flex items-center gap-2 text-[15px] font-semibold text-crimson hover:underline" href={`#/missions/${missionId}/atelier/${gate[1]}`} target="_blank" rel="noreferrer">
          Voir le résultat de l’atelier {gate[1]} avant de décider <ArrowRight className="h-4 w-4" />
        </a>
      )}

      {prompt.kind === 'yesno' && (
        <div className="mt-6 flex flex-wrap gap-3">
          <button className="btn-primary" onClick={() => onAnswer('oui')}>
            <Check className="h-4 w-4" /> {approval ? 'Approuver' : 'Oui'}
          </button>
          <button className="btn-quiet" onClick={() => onAnswer('non')}>
            {approval ? 'Refuser' : 'Non'}
          </button>
        </div>
      )}

      {prompt.kind === 'choice' && (
        <div className="mt-6 flex flex-col gap-3">
          {prompt.options.map((o) => (
            <button key={o.key} className="btn-quiet !justify-start !rounded-2xl !py-4 text-left" onClick={() => onAnswer(o.key)}>
              <span className="mono mr-2 font-bold text-crimson">{o.key}</span> {o.label}
            </button>
          ))}
        </div>
      )}

      {prompt.kind === 'text' && (
        <form
          className="mt-6"
          onSubmit={(e) => {
            e.preventDefault()
            onAnswer(text)
          }}
        >
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                onAnswer(text)
              }
            }}
            rows={2}
            autoFocus
            placeholder="Votre réponse — Entrée pour envoyer"
            className="w-full resize-y rounded-2xl border border-line-strong bg-ground px-5 py-4 text-[17px] outline-none focus:border-crimson"
          />
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="submit" className="btn-primary">
              {text.trim() ? 'Envoyer' : 'Continuer sans réponse'}
            </button>
            {prompt.confirm && (
              <button type="button" className="btn-quiet" onClick={() => onAnswer('CONFIRMER')}>
                CONFIRMER
              </button>
            )}
          </div>
        </form>
      )}
    </section>
  )
}

function usePilot(missionId: string) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [state, setState] = useState<PilotState | null>(null)
  const [lines, setLines] = useState<string[]>([])
  const [error, setError] = useState('')
  const after = useRef(0)

  useEffect(() => {
    api.currentPilot(missionId).then((r) => r.session_id && setSessionId(r.session_id), () => undefined)
  }, [missionId])

  useEffect(() => {
    if (!sessionId) return
    let alive = true
    after.current = 0
    setLines([])
    const tick = async () => {
      try {
        const s = await api.pilot(sessionId, after.current)
        if (!alive) return
        after.current = s.next
        if (s.lines.length) setLines((l) => [...l, ...s.lines])
        setState(s)
      } catch (e) {
        if (alive) setError((e as Error).message)
      }
    }
    tick()
    const timer = setInterval(() => {
      if (state?.status && state.status !== 'running') return
      tick()
    }, 1000)
    return () => {
      alive = false
      clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, state?.status])

  const start = useCallback(async (seance = false) => {
    setError('')
    try {
      setState(null)
      setSessionId((await api.startPilot(missionId, seance)).session_id)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [missionId])

  return { sessionId, setSessionId, state, lines, error, setError, start }
}

export default function Pilot() {
  const { id = '' } = useParams()
  const mission = useAsync(() => api.mission(id), [id])
  const pilot = usePilot(id)
  const [seance, setSeance] = useState(false)
  const { state, sessionId } = pilot

  if (mission.loading) return <Loading />
  if (mission.error || !mission.data) return <Failure message={mission.error} />

  const step = mission.data.next_step
  const running = state?.status === 'running'
  const waiting = running && state?.prompt != null
  const org = mission.data.organisation.nom || mission.data.mission.name

  const answer = async (text: string) => {
    if (!sessionId || !state?.prompt) return
    try {
      await api.answer(sessionId, state.prompt.id, text)
    } catch (e) {
      pilot.setError((e as Error).message)
    }
  }
  const stop = async () => {
    if (!sessionId) return
    try {
      await api.stopPilot(sessionId)
    } catch (e) {
      pilot.setError((e as Error).message)
    }
  }

  return (
    <>
      <PageHead eyebrow={`Mission · ${org}`} title="Piloter la mission" lead="Comme dans le terminal : l’agent travaille, vous décidez à chaque étape. Rien n’est approuvé sans vous." />

      {!sessionId && (
        <section className="rise-2 sheet px-10 py-10">
          <Kicker>Prochaine étape</Kicker>
          <p className="mt-2 font-display text-[30px] font-bold leading-tight [font-stretch:104%]">{step.label}</p>
          {step.can_pilot ? (
            <>
              <label className="mt-6 flex cursor-pointer items-start gap-3 text-[16px] text-ink-soft">
                <input type="checkbox" checked={seance} onChange={(e) => setSeance(e.target.checked)} className="mt-1 h-5 w-5 accent-[#BE1E2D]" />
                <span>
                  <b className="font-semibold text-ink">Séance avec le client</b> (ateliers 4 et 5) : l’agent vous pose les questions que seul le client peut éclairer.
                </span>
              </label>
              <button className="btn-primary mt-6" onClick={() => pilot.start(seance)}>
                Continuer la mission <ArrowRight className="h-4 w-4" />
              </button>
            </>
          ) : (
            <p className="mt-4 max-w-[56ch] text-[17px] text-ink-soft">
              {step.action === 'generate_report' || step.action === 'done' ? (
                <>
                  Rien à lancer ici. <Link className="font-semibold text-crimson hover:underline" to={`/missions/${id}/rapports`}>Passer aux rapports</Link>.
                </>
              ) : (
                'Cette mission ne peut pas avancer d’ici : sa collecte de contexte n’est pas terminée. Créez-la à nouveau depuis « Nouvelle mission ».'
              )}
            </p>
          )}
        </section>
      )}

      {sessionId && (
        <>
          <div className="rise-2 mb-5 flex flex-wrap items-center justify-between gap-4">
            <p className="flex items-center gap-3 text-[17px] font-semibold">
              {running && !waiting && <Loader2 className="h-5 w-5 animate-spin text-crimson" />}
              {running && !waiting && 'L’agent travaille…'}
              {waiting && <span className="text-crimson">En attente de votre réponse</span>}
              {state?.status === 'done' && <span className="text-ok">Session terminée</span>}
              {state?.status === 'stopped' && <span className="text-ink-soft">Session interrompue — tout est conservé</span>}
              {state?.status === 'error' && <span className="text-crimson">La session s’est arrêtée sur une erreur</span>}
              {!state && 'Connexion…'}
            </p>
            {running && (
              <button className="btn-quiet !py-2" onClick={stop}>
                <Square className="h-4 w-4" /> Interrompre
              </button>
            )}
          </div>

          <Journal lines={pilot.lines} choicePending={waiting && state?.prompt?.kind === 'choice'} />
          {waiting && state?.prompt && <PromptCard prompt={state.prompt} missionId={id} lines={pilot.lines} onAnswer={answer} />}

          {state && state.files.length > 0 && sessionId && (
            <section className="sheet rise mt-6 px-8 py-7">
              <Kicker>Les cinq ateliers sont approuvés</Kicker>
              <p className="mt-1 font-display text-[22px] font-extrabold">Les rapports sont prêts</p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                {[['rapport', 'Rapport de mission'], ['annexe', 'Annexe d’audit']].filter(([k]) => state.files.includes(k)).map(([kind, label]) => (
                  <div key={kind}>
                    <p className="text-[15px] font-semibold">{label}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <a className="btn-primary !py-2" href={api.pilotFileUrl(sessionId, kind)} download>
                        <Download className="h-4 w-4" /> Word
                      </a>
                      <a className="btn-quiet !py-2" href={api.pilotFileUrl(sessionId, kind, 'pdf')} download title="Demande à Word ou LibreOffice : quelques secondes">
                        <Download className="h-4 w-4" /> PDF
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {state && state.status !== 'running' && (
            <div className="mt-6 flex flex-wrap gap-3">
              <Link className="btn-primary" to={`/missions/${id}`}>
                Voir la mission
              </Link>
              {state.status !== 'done' || state.final_status !== 'all_approved' ? (
                <button className="btn-quiet" onClick={() => pilot.start(seance)}>
                  Continuer la mission
                </button>
              ) : null}
              {state.final_status === 'all_approved' && (
                <Link className="btn-quiet" to={`/missions/${id}/rapports`}>
                  Produire les rapports
                </Link>
              )}
            </div>
          )}
        </>
      )}

      {pilot.error && (
        <div className="mt-6">
          <Failure message={pilot.error} />
        </div>
      )}
    </>
  )
}
