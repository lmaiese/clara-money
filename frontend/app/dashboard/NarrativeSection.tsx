'use client'
import type { Narratives } from '@/lib/types'

interface Props {
  narratives: Narratives | null
  ready: boolean
}

export function NarrativeSection({ narratives, ready }: Props) {
  if (!ready || !narratives) {
    return (
      <div className="narrative-section">
        <div className="narrative-header">✦ Clara sta analizzando il tuo profilo...</div>
        <div className="skeleton-line"></div>
        <div className="skeleton-line" style={{ width: '85%' }}></div>
        <div className="skeleton-line" style={{ width: '70%' }}></div>
      </div>
    )
  }

  return (
    <div className="narrative-section">
      <div className="narrative-header">✦ Clara</div>
      <p className="narrative-intro">{narratives.intro}</p>
      <div className="narrative-scenarios">
        <p><strong>Sicuro:</strong> {narratives.sicuro}</p>
        <p><strong>Bilanciato:</strong> {narratives.bilanciato}</p>
        <p><strong>Crescita:</strong> {narratives.crescita}</p>
      </div>
    </div>
  )
}
