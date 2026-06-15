'use client'
import { useState } from 'react'
import { step1Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { age: number; monthly_income: number }) => void
  error: string | null
}

export function Step1({ onNext, error }: Props) {
  const [age, setAge] = useState('')
  const [income, setIncome] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  function handleSubmit() {
    const result = step1Schema.safeParse({
      age: Number(age),
      monthly_income: Number(income),
    })
    if (!result.success) {
      const errs: Record<string, string> = {}
      result.error.issues.forEach(e => { errs[String(e.path[0])] = e.message })
      setFieldErrors(errs)
      return
    }
    setFieldErrors({})
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Quanti anni hai e qual è il tuo reddito netto mensile?</h2>
      <p className="step-hint">Reddito netto = quello che ricevi in busta paga.</p>

      <div className="field">
        <label>Età</label>
        <input
          type="number"
          placeholder="es. 32"
          value={age}
          onChange={e => setAge(e.target.value)}
        />
        {fieldErrors.age && <span className="field-error">{fieldErrors.age}</span>}
      </div>

      <div className="field">
        <label>Reddito netto mensile (€)</label>
        <div className="chips">
          {['< 1.500€', '1.500–2.500€', '2.500–4.000€', '> 4.000€'].map(label => (
            <button key={label} className="chip" type="button"
              onClick={() => {
                const map: Record<string, string> = {
                  '< 1.500€': '1200', '1.500–2.500€': '2000',
                  '2.500–4.000€': '3000', '> 4.000€': '4500',
                }
                setIncome(map[label])
              }}
            >{label}</button>
          ))}
        </div>
        <input
          type="number"
          placeholder="oppure importo esatto"
          value={income}
          onChange={e => setIncome(e.target.value)}
        />
        {fieldErrors.monthly_income && <span className="field-error">{fieldErrors.monthly_income}</span>}
      </div>

      {error && <p className="api-error">{error}</p>}
      <button className="btn-primary" onClick={handleSubmit}>Avanti →</button>
    </div>
  )
}
