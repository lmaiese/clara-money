'use client'
import { useState, useEffect } from 'react'
import { apiFetch, ApiError } from '@/lib/api'
import { GOAL_HORIZON, StepData } from '@/lib/validation'

type FormData = Partial<{
  age: number
  monthly_income: number
  monthly_expenses: number
  liquid_savings: number
  existing_investments: number
  goal: 'growth' | 'house' | 'pension'
  horizon_years: number
}>

interface ProfileResponse {
  onboarding_step: number
}

export function useWizard() {
  const [currentStep, setCurrentStep] = useState(0)
  const [formData, setFormData] = useState<FormData>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<ProfileResponse>('/profiles/me')
      .then(p => setCurrentStep(p.onboarding_step))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function next(stepData: StepData) {
    setError(null)
    const newStep = currentStep + 1
    const patch: Record<string, unknown> = { ...stepData, onboarding_step: newStep }

    if ('goal' in stepData && stepData.goal) {
      patch.horizon_years = GOAL_HORIZON[stepData.goal]
    }

    try {
      await apiFetch('/profiles/me', {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      setFormData(prev => ({ ...prev, ...stepData }))
      setCurrentStep(newStep)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        window.location.href = '/auth?redirect=/onboarding'
        return
      }
      setError('Errore di rete, riprova')
    }
  }

  function back() {
    setCurrentStep(prev => Math.max(0, prev - 1))
  }

  return { currentStep, formData, loading, error, next, back }
}
