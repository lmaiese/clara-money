'use client'
import { useState } from 'react'
import { step4Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { existing_investments: number }) => void
  onBack: () => void
  error: string | null
}

export function Step4({ onNext, onBack, error }: Props) {
  const [investments, setInvestments] = useState('')
  const [fieldError, setFieldError] = useState('')

  const CHIPS = [
    { label: 'Nessuno (0€)', value: '0' },
    { label: '< 10.000€', value: '5000' },
    { label: '10.000–50.000€', value: '25000' },
    { label: '> 50.000€', value: '60000' },
  ]

  function handleSubmit() {
    const result = step4Schema.safeParse({ existing_investments: Number(investments) })
    if (!result.success) { setFieldError(result.error.issues[0].message); return }
    setFieldError('')
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Hai già investimenti?</h2>
      <p className="step-hint">Fondo pensione, ETF, BTP, azioni. Stima il valore totale attuale. Zero se nessuno.</p>
      <div className="chips">
        {CHIPS.map(c => (
          <button key={c.value} className="chip" type="button" onClick={() => setInvestments(c.value)}>
            {c.label}
          </button>
        ))}
      </div>
      <input type="number" placeholder="oppure importo esatto (€)"
        value={investments} onChange={e => setInvestments(e.target.value)} />
      {fieldError && <span className="field-error">{fieldError}</span>}
      {error && <p className="api-error">{error}</p>}
      <div className="step-nav">
        <button className="btn-secondary" onClick={onBack}>← Indietro</button>
        <button className="btn-primary" onClick={handleSubmit}>Avanti →</button>
      </div>
    </div>
  )
}
