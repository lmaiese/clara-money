export interface MathData {
  sicuro: number[]
  bilanciato: number[]
  crescita: number[]
  inflazione: number[]
  labels: number[]
}

export interface Narratives {
  intro: string
  sicuro: string
  bilanciato: string
  crescita: string
}

export interface Source {
  title: string
  source: string
}

export interface ScenarioResponse {
  scenario_id: string
  math_data: MathData
  narratives: Narratives | null
  narrative_ready: boolean
  generated_at: string
  sources: Source[] | null
}

export interface User {
  id: string
  email: string
  plan: 'free' | 'pro'
}
