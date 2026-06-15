'use client'
import type { MathData } from '@/lib/types'
import { PaywallGate } from './PaywallGate'

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

function relativePercent(value: number, base: number): string {
  return `+${Math.round((value / base - 1) * 100)}%`
}

interface Props {
  mathData: MathData
  plan: 'free' | 'pro'
}

export function ScenarioCards({ mathData, plan }: Props) {
  const sicuroFinal = mathData.sicuro[mathData.sicuro.length - 1]

  return (
    <div className="scenario-cards">
      {SCENARIOS.map(({ key, label, rate, risk, color }) => {
        const finalValue = mathData[key][mathData[key].length - 1]
        const isLocked = plan === 'free' && key !== 'sicuro'

        if (isLocked) {
          return (
            <PaywallGate
              key={key}
              label={label}
              rate={rate}
              risk={risk}
              color={color}
              relativeValue={relativePercent(finalValue, sicuroFinal)}
            />
          )
        }

        return (
          <div key={key} className="scenario-card" style={{ borderTopColor: color }}>
            <div className="scenario-label">{label} · {rate}</div>
            <div className="scenario-value">{formatEur(finalValue)}</div>
            <div className="scenario-risk">Rischio: {risk}</div>
          </div>
        )
      })}
    </div>
  )
}
