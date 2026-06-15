'use client'

const STEP_LABELS = [
  'Età e reddito',
  'Spese mensili',
  'Risparmi',
  'Investimenti',
  'Obiettivo',
]

interface Props {
  currentStep: number  // 0-4 (passo corrente mostrato, non completati)
  total?: number
}

export function WizardProgress({ currentStep, total = 5 }: Props) {
  return (
    <div className="wizard-progress">
      <div className="progress-header">
        <span className="progress-label">Il tuo profilo</span>
        <span className="progress-count">{currentStep + 1} / {total}</span>
      </div>
      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{ width: `${((currentStep + 1) / total) * 100}%` }}
        />
      </div>
      <div className="progress-steps">
        {STEP_LABELS.map((label, i) => (
          <span
            key={i}
            className={
              i < currentStep ? 'step-done' :
              i === currentStep ? 'step-current' :
              'step-pending'
            }
          >
            {i < currentStep ? `✓ ${label}` : label}
          </span>
        ))}
      </div>
    </div>
  )
}
