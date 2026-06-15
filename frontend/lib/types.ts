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

export interface ScenarioResponse {
  scenario_id: string
  math_data: MathData
  narratives: Narratives | null
  narrative_ready: boolean
  generated_at: string
}
