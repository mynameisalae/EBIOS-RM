import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Loader2, Plus, X } from 'lucide-react'
import { api } from '../lib/api'
import { Failure, Kicker, PageHead } from '../components/kit'

function Drop({ title, hint, multiple, files, onFiles, required }: { title: string; hint: string; multiple?: boolean; files: File[]; onFiles: (f: File[]) => void; required?: boolean }) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <div className="sheet px-8 py-7">
      <div className="flex items-baseline justify-between gap-4">
        <p className="font-display text-[20px] font-extrabold [font-stretch:108%]">{title}</p>
        <Kicker>{required ? 'Obligatoire' : 'Facultatif'}</Kicker>
      </div>
      <p className="mt-1 max-w-[56ch] text-[16px] text-ink-mute">{hint}</p>
      <input ref={input} type="file" accept=".docx,.md,.txt,.pdf" multiple={multiple} className="hidden" onChange={(e) => onFiles([...(multiple ? files : []), ...Array.from(e.target.files ?? [])])} />
      <ul className="mt-4 space-y-2">
        {files.map((f, i) => (
          <li key={`${f.name}-${i}`} className="flex items-center gap-3 rounded-xl bg-ground px-4 py-2.5 text-[16px]">
            <FileText className="h-4 w-4 flex-none text-crimson" />
            <span className="min-w-0 flex-1 truncate font-semibold">{f.name}</span>
            <button aria-label={`Retirer ${f.name}`} className="text-ink-mute hover:text-crimson" onClick={() => onFiles(files.filter((_, j) => j !== i))}>
              <X className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
      {(multiple || files.length === 0) && (
        <button className="mt-4 inline-flex items-center gap-2 text-[16px] font-semibold text-crimson hover:underline" onClick={() => input.current?.click()}>
          <Plus className="h-4 w-4" /> {files.length === 0 ? 'Choisir un fichier' : 'Ajouter un fichier'}
        </button>
      )}
    </div>
  )
}

export default function NewMission() {
  const navigate = useNavigate()
  const [questionnaire, setQuestionnaire] = useState<File[]>([])
  const [supporting, setSupporting] = useState<File[]>([])
  const [seance, setSeance] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const launch = async () => {
    setBusy(true)
    setError('')
    try {
      const started = await api.newMission(questionnaire[0], supporting, seance)
      navigate(`/missions/${started.mission_id}/pilote`)
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
    }
  }

  return (
    <>
      <PageHead
        eyebrow="Nouvelle mission"
        title="Démarrer une analyse"
        lead="Déposez le questionnaire de contexte rempli par l’organisation, avec ses documents si vous en avez. L’agent en extrait les faits ; vous validez ce qui est douteux, puis les cinq ateliers s’enchaînent."
      />
      <div className="rise-2 space-y-6">
        <Drop title="Questionnaire de contexte rempli" hint="Le document Word, Markdown, texte ou PDF renvoyé par l’organisation." files={questionnaire} onFiles={setQuestionnaire} required />
        <Drop title="Documents complémentaires" hint="Politique de sécurité, schéma d’architecture, rapport d’audit précédent… L’agent y cherche les réponses manquantes." multiple files={supporting} onFiles={setSupporting} />
      </div>

      <label className="sheet mt-6 flex cursor-pointer items-start gap-4 px-8 py-6">
        <input type="checkbox" checked={seance} onChange={(e) => setSeance(e.target.checked)} className="mt-1.5 h-5 w-5 accent-[#BE1E2D]" />
        <span>
          <span className="block font-display text-[18px] font-extrabold">Séance avec le client (ateliers 4 et 5)</span>
          <span className="mt-1 block text-[15px] text-ink-soft">
            L’agent vous pose les questions que seul le client peut éclairer avant ces deux ateliers. Sans cette case, il travaille avec le contexte déjà collecté.
          </span>
        </span>
      </label>

      <div className="mt-10 flex items-center gap-5">
        <button className="btn-primary disabled:opacity-50" disabled={questionnaire.length === 0 || busy} onClick={launch}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          Lancer la mission
        </button>
        <p className="text-[15px] text-ink-mute">L’agent utilisera le modèle configuré dans .env.</p>
      </div>
      {error && (
        <div className="mt-6">
          <Failure message={error} />
        </div>
      )}
    </>
  )
}
