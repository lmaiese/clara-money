'use client'
import type { Source } from '@/lib/types'

interface Props {
  sources: Source[] | null
}

export function SourcesSection({ sources }: Props) {
  if (!sources || sources.length === 0) return null

  return (
    <details className="sources-section">
      <summary className="sources-summary">Basato su fonti normative</summary>
      <ul className="sources-list">
        {sources.map((s, i) => (
          <li key={i} className="sources-item">
            <span className="sources-title">{s.title}</span>
            <span className="sources-badge">{s.source}</span>
          </li>
        ))}
      </ul>
    </details>
  )
}
