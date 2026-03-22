// Shared types matching the backend Pydantic models

export type SkillStatus = "live" | "coming_soon"

export type DisplayHintType = "gauge" | "percentile" | "badge" | "score_table" | "text"

export interface DisplayHint {
  type: DisplayHintType
  label: string
  min?: number
  max?: number
}

export type DisplayMap = Record<string, DisplayHint>

export interface SkillCard {
  name: string
  description: string
  version: string
  input_schema: Record<string, unknown>
  output_keys: string[]
  config: Record<string, unknown>
  trigger_modes: TriggerMode[]
  roles: { operator: RoleConfig; participant: RoleConfig }
  setup_prompt: string
  user_display: DisplayMap
}

export interface TriggerMode {
  mode: "threshold" | "manual" | "instant"
  description?: string
}

export interface RoleConfig {
  can_trigger?: boolean
  can_view_all?: boolean
  can_view_own?: boolean
}

// /init
export interface InitRequest {
  skill_name: string
  message: string
  instance_id?: string
}

export interface InitResponse {
  instance_id: string
  status: "configuring" | "ready"
  message: string
  admin_token?: string
}

// /submit
export interface SubmitResponse {
  submission_id: string
  status: "received_pending" | "received_analysis_complete"
  submissions_count: number
  threshold?: number
}

// /results
export interface NoveltyResult {
  submission_id: string
  novelty_score: number
  percentile: number
  cluster: string
  criteria_scores: Record<string, number>
  status: "analyzed" | "duplicate" | "quick_scored"
  analysis_depth: "full" | "quick" | "flagged"
  duplicate_of: string | null
  enclave_signature?: string
  attestation_quote?: string
}

// /attestation
export interface AttestationResponse {
  quote: string
  verify_url: string
}

// /health
export interface HealthResponse {
  status: string
  instances: number
  submissions: number
  skills: string[]
}

// Frontend-only: Instance state stored in localStorage
export interface StoredInstance {
  instance_id: string
  skill_name: string
  admin_token: string
  created_at: string
}
