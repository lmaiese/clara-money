import { z } from 'zod'

export const GOAL_HORIZON: Record<string, number> = {
  growth: 15,
  house: 5,
  pension: 20,
}

export const step1Schema = z.object({
  age: z.number().int().min(18, 'Età minima 18 anni').max(75, 'Età massima 75 anni'),
  monthly_income: z.number().int().min(1).max(50000, 'Massimo 50.000€'),
})

export const step2Schema = z.object({
  monthly_expenses: z.number().int().min(1, 'Inserisci un importo valido'),
})

export const step3Schema = z.object({
  liquid_savings: z.number().int().min(0),
})

export const step4Schema = z.object({
  existing_investments: z.number().int().min(0),
})

export const step5Schema = z.object({
  goal: z.enum(['growth', 'house', 'pension']),
})

export type StepData =
  | z.infer<typeof step1Schema>
  | z.infer<typeof step2Schema>
  | z.infer<typeof step3Schema>
  | z.infer<typeof step4Schema>
  | z.infer<typeof step5Schema>
