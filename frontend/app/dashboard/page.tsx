'use client'
import dynamic from 'next/dynamic'
import { useDashboard } from './useDashboard'
import { ScenarioCards } from './ScenarioCards'
import { NarrativeSection } from './NarrativeSection'
import { SourcesSection } from './SourcesSection'

const ScenarioChart = dynamic(
  () => import('./ScenarioChart').then(m => ({ default: m.ScenarioChart })),
  { ssr: false }
)

export default function DashboardPage() {
  const state = useDashboard()

  if (state.status === 'loading') {
    return <main className="loading">Calcolo scenari in corso...</main>
  }

  if (state.status === 'error') {
    return (
      <main className="dashboard-layout">
        <p className="api-error">{state.message}</p>
      </main>
    )
  }

  const mathData = state.mathData
  const narratives = state.status === 'narrative_ready' ? state.narratives : null
  const sources = state.status === 'narrative_ready' ? state.sources : null
  const ready = state.status === 'narrative_ready'

  return (
    <main className="dashboard-layout">
      <h1>I tuoi scenari</h1>
      <ScenarioCards mathData={mathData} />
      <ScenarioChart mathData={mathData} />
      <NarrativeSection narratives={narratives} ready={ready} />
      <SourcesSection sources={sources} />
    </main>
  )
}
