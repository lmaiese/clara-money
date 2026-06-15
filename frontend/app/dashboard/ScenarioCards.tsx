'use client'
import type { MathData } from '@/lib/types'

const SCENARIOS = [
  { key: 'sicuro' as const, label: 'Sicuro', rate: '3.5%', risk: 'Basso', color: '#86efac' },
  { key: 'bilanciato' as const, label: 'Bilanciato', rate: '5%', risk: 'Medio', color: '#4ade80' },
  { key: 'crescita' as const, label: 'Crescita', rate: '7%', risk: 'Alto', color: '#059669' },
] as const

function formatEur(value: number): string {
  return new Intl.NumberFormat('it-IT', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value)
}

interface Props {
  mathData: MathData
}

export function ScenarioCards({ mathData }: Props) {
  return (
    <div className="scenario-cards">
      {SCENARIOS.map(({ key, label, rate, risk, color }) => (
        <div key={key} className="scenario-card" style={{ borderTopColor: color }}>
          <div className="scenario-label">{label} · {rate}</div>
          <div className="scenario-value">{formatEur(mathData[key][mathData[key].length - 1])}</div>
          <div className="scenario-risk">Rischio: {risk}</div>
        </div>
      ))}
    </div>
  )
}
