'use client'
import { useState } from 'react'
import { step3Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { liquid_savings: number }) => void
  onBack: () => void
  error: string | null
}

export function Step3({ onNext, onBack, error }: Props) {
  const [savings, setSavings] = useState('')
  const [fieldError, setFieldError] = useState('')

  const CHIPS = [
    { label: '< 5.000€', value: '3000' },
    { label: '5.000–20.000€', value: '12000' },
    { label: '20.000–50.000€', value: '35000' },
    { label: '> 50.000€', value: '60000' },
  ]

  function handleSubmit() {
    const result = step3Schema.safeParse({ liquid_savings: Number(savings) })
    if (!result.success) { setFieldError(result.error.issues[0].message); return }
    setFieldError('')
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Quanto hai risparmiato oggi?</h2>
      <p className="step-hint">Liquidità disponibile: conto corrente + conto deposito. Stima.</p>
      <div className="chips">
        {CHIPS.map(c => (
          <button key={c.value} className="chip" type="button" onClick={() => setSavings(c.value)}>
            {c.label}
          </button>
        ))}
      </div>
      <input type="number" placeholder="oppure importo esatto (€)"
        value={savings} onChange={e => setSavings(e.target.value)} />
      {fieldError && <span className="field-error">{fieldError}</span>}
      {error && <p className="api-error">{error}</p>}
      <div className="step-nav">
        <button className="btn-secondary" onClick={onBack}>← Indietro</button>
        <button className="btn-primary" onClick={handleSubmit}>Avanti →</button>
      </div>
    </div>
  )
}
