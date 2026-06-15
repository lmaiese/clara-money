'use client'
import { useRouter } from 'next/navigation'
import { useWizard } from './useWizard'
import { WizardProgress } from './WizardProgress'
import { Step1 } from './steps/Step1'
import { Step2 } from './steps/Step2'
import { Step3 } from './steps/Step3'
import { Step4 } from './steps/Step4'
import { Step5 } from './steps/Step5'

export default function OnboardingPage() {
  const router = useRouter()
  const { currentStep, loading, error, next, back } = useWizard()

  if (loading) return <div className="loading">Caricamento...</div>
  if (currentStep >= 5) { router.replace('/dashboard'); return null }

  const stepProps = { error, onBack: back }

  return (
    <main className="onboarding-layout">
      <WizardProgress currentStep={currentStep} />
      {currentStep === 0 && <Step1 onNext={next} error={error} />}
      {currentStep === 1 && <Step2 onNext={next} {...stepProps} />}
      {currentStep === 2 && <Step3 onNext={next} {...stepProps} />}
      {currentStep === 3 && <Step4 onNext={next} {...stepProps} />}
      {currentStep === 4 && <Step5 onNext={next} {...stepProps} />}
    </main>
  )
}
