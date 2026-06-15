'use client'
import { useState } from 'react'
import { step5Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { goal: 'growth' | 'house' | 'pension' }) => void
  onBack: () => void
  error: string | null
}

const GOALS = [
  {
    key: 'growth' as const,
    title: 'Crescere i risparmi',
    desc: 'Voglio che i miei soldi lavorino nel lungo periodo.',
    horizon: '~15 anni',
  },
  {
    key: 'house' as const,
    title: 'Comprare casa',
    desc: 'Sto accumulando per un acquisto immobiliare.',
    horizon: '~5 anni',
  },
  {
    key: 'pension' as const,
    title: 'Pensare alla pensione',
    desc: 'Voglio costruire una rendita integrativa.',
    horizon: '~20 anni',
  },
]

export function Step5({ onNext, onBack, error }: Props) {
  const [selected, setSelected] = useState<'growth' | 'house' | 'pension' | null>(null)
  const [fieldError, setFieldError] = useState('')

  function handleSubmit() {
    const result = step5Schema.safeParse({ goal: selected })
    if (!result.success) { setFieldError('Seleziona un obiettivo per continuare.'); return }
    setFieldError('')
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Qual è il tuo obiettivo principale?</h2>
      <p className="step-hint">Scegli quello che ti rappresenta di più.</p>
      <div className="goal-cards">
        {GOALS.map(g => (
          <button
            key={g.key}
            className={`goal-card ${selected === g.key ? 'selected' : ''}`}
            onClick={() => setSelected(g.key)}
          >
            <strong>{g.title}</strong>
            <span>{g.desc}</span>
            <small>Orizzonte temporale consigliato: {g.horizon}</small>
          </button>
        ))}
      </div>
      {fieldError && <span className="field-error">{fieldError}</span>}
      {error && <p className="api-error">{error}</p>}
      <div className="step-nav">
        <button className="btn-secondary" onClick={onBack}>← Indietro</button>
        <button className="btn-primary" onClick={handleSubmit}>Vedi i miei scenari →</button>
      </div>
    </div>
  )
}
