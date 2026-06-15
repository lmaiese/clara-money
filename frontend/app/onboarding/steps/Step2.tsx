'use client'
import { useState } from 'react'
import { step2Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { monthly_expenses: number }) => void
  onBack: () => void
  error: string | null
}

export function Step2({ onNext, onBack, error }: Props) {
  const [expenses, setExpenses] = useState('')
  const [fieldError, setFieldError] = useState('')

  const CHIPS = [
    { label: '< 800€', value: '600' },
    { label: '800–1.200€', value: '1000' },
    { label: '1.200–1.800€', value: '1500' },
    { label: '> 1.800€', value: '2200' },
  ]

  function handleSubmit() {
    const result = step2Schema.safeParse({ monthly_expenses: Number(expenses) })
    if (!result.success) { setFieldError(result.error.issues[0].message); return }
    setFieldError('')
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Quanto spendi ogni mese?</h2>
      <p className="step-hint">Stima approssimativa — affitto, cibo, trasporti, svago.</p>
      <div className="chips">
        {CHIPS.map(c => (
          <button key={c.value} className="chip" type="button" onClick={() => setExpenses(c.value)}>
            {c.label}
          </button>
        ))}
      </div>
      <input type="number" placeholder="oppure importo esatto (€)"
        value={expenses} onChange={e => setExpenses(e.target.value)} />
      {fieldError && <span className="field-error">{fieldError}</span>}
      {error && <p className="api-error">{error}</p>}
      <div className="step-nav">
        <button className="btn-secondary" onClick={onBack}>← Indietro</button>
        <button className="btn-primary" onClick={handleSubmit}>Avanti →</button>
      </div>
    </div>
  )
}
