import { useEffect, useState } from 'react'

export type AtelierState = 'approved' | 'in_progress' | 'absent'

export interface MissionSummary {
  id: string; name: string; status: string; organisation: string; secteur: string
  updated_at: string; approved: number; ateliers: { n: number; state: AtelierState }[]
}
export interface AtelierOverview {
  n: number; label: string; question: string; state: AtelierState; version: number | null
  versions: number; updated_at: string | null; headline: string; metrics: { label: string; value: number }[]
}
export interface MissionOverview {
  mission: { id: string; name: string; status: string; created_at: string; updated_at: string }
  organisation: { nom?: string; secteur?: string; referentiels?: string[] }
  attck_version: string | null; ateliers: AtelierOverview[]
  decisions: number; model_calls: number; can_write_report: boolean
}
export interface AtelierDetail {
  n: number; label: string; question: string; state: AtelierState; headline: string
  metrics: { label: string; value: number }[]
  versions: { number: number; status: string; created_at: string }[]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  output: Record<string, any> | null
  organisation: { nom?: string }
}
export interface ProjectFacts {
  ateliers: { n: number; label: string; question: string }[]
  frameworks: { id: string; name: string; version: string; controls: number }[]
  controls: number
  attack: { version: string; techniques: number; mitigations: number } | null
  activity: { first: string; last: string; commits: number; weeks: { week: number; commits: number }[] } | null
}
export interface Job {
  id: string; status: 'running' | 'done' | 'error'; lines: string[]; error: string
  summary: null | {
    sections: number; statements: number; corrected: number
    rejected: { section: string; text: string; reason: string }[]
    skipped: { title: string; reason: string }[]
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? response.statusText)
  }
  return response.json()
}

export const api = {
  missions: () => request<MissionSummary[]>('/api/missions'),
  mission: (id: string) => request<MissionOverview>(`/api/missions/${id}`),
  atelier: (id: string, n: number) => request<AtelierDetail>(`/api/missions/${id}/ateliers/${n}`),
  project: () => request<ProjectFacts>('/api/projet'),
  startReport: (id: string, annex?: File) => {
    const form = new FormData()
    if (annex) form.append('annexe', annex)
    return request<{ job_id: string; appraisals: number }>(`/api/missions/${id}/rapport`, { method: 'POST', body: form })
  },
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  annexUrl: (id: string) => `/api/missions/${id}/annexe`,
  jobFileUrl: (jobId: string) => `/api/jobs/${jobId}/fichier`,
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): { data: T | null; error: string; loading: boolean } {
  const [state, setState] = useState<{ data: T | null; error: string; loading: boolean }>({ data: null, error: '', loading: true })
  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true, error: '' }))
    load().then(
      (data) => alive && setState({ data, error: '', loading: false }),
      (e: Error) => alive && setState({ data: null, error: e.message, loading: false }),
    )
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}
