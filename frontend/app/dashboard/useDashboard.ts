'use client'
import { useState, useEffect } from 'react'
import { apiFetch, ApiError } from '@/lib/api'
import type { MathData, Narratives, ScenarioResponse } from '@/lib/types'

type DashboardState =
  | { status: 'loading' }
  | { status: 'math_ready'; mathData: MathData }
  | { status: 'narrative_ready'; mathData: MathData; narratives: Narratives }
  | { status: 'error'; message: string }

export function useDashboard(): DashboardState {
  const [state, setState] = useState<DashboardState>({ status: 'loading' })

  useEffect(() => {
    let stopped = false

    async function run() {
      try {
        const generated = await apiFetch<ScenarioResponse>('/scenarios/generate', { method: 'POST' })
        if (stopped) return
        setState({ status: 'math_ready', mathData: generated.math_data })

        while (!stopped) {
          await new Promise(r => setTimeout(r, 2000))
          if (stopped) break
          const latest = await apiFetch<ScenarioResponse>('/scenarios/me')
          if (latest.narrative_ready && latest.narratives) {
            setState({ status: 'narrative_ready', mathData: latest.math_data, narratives: latest.narratives })
            return
          }
        }
      } catch (err) {
        if (!stopped) {
          setState({
            status: 'error',
            message: err instanceof ApiError ? err.message : 'Errore di rete',
          })
        }
      }
    }

    run()
    return () => { stopped = true }
  }, [])

  return state
}
