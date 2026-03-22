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
  user_token?: string
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
  aligned?: boolean
  criteria_scores: Record<string, number>
  status: "analyzed" | "duplicate"
  analysis_depth: "full" | "flagged"
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

// ---------------------------------------------------------------------------
// Procurement types
// ---------------------------------------------------------------------------

export interface BuyerPolicy {
  required_columns: string[]
  min_row_count: number
  max_null_rate: number
  max_duplicate_rate: number
  min_label_rate?: number
  forbidden_columns: string[]
  seller_claim_checks: string[]
  milestone_weights: Record<string, number>
  max_budget: number
  allowed_pre_purchase_outputs: string[]
  release_mode: "immediate" | "manual"
  renegotiation_enabled: boolean
}

export interface SellerClaim {
  name: string
  value: string | number
}

export interface SupplierSubmission {
  dataset_name: string
  dataset_reference?: string
  seller_claims: SellerClaim[]
  metadata: Record<string, string>
  reserve_price: number
  note?: string
}

export interface HardConstraintResult {
  name: string
  passed: boolean
  detail?: string
}

export interface MilestoneScore {
  name: string
  weight: number
  score: number
  passed: boolean
}

export interface DatasetMetrics {
  row_count: number
  null_rate: number
  duplicate_rate: number
  column_count: number
  columns_present: string[]
  columns_missing: string[]
}

export type NegotiationState =
  | "none"
  | "requested_by_buyer"
  | "requested_by_seller"
  | "awaiting_counterparty"
  | "renegotiation_submitted"
  | "accepted"
  | "rejected"

export interface NegotiationStatus {
  state: NegotiationState
  revised_budget?: number
  revised_reserve?: number
  used: boolean
}

export type SettlementState = "pending" | "authorized" | "failed" | "none"

export interface SettlementStatus {
  state: SettlementState
  amount?: number
}

export interface ReleaseToken {
  token: string
  issued_at: string
  expires_at?: string
}

export interface ProcurementResult {
  submission_id: string
  hard_constraints: HardConstraintResult[]
  milestones: MilestoneScore[]
  claim_results: Record<string, boolean>
  partial_score: number
  proposed_payment: number
  negotiation: NegotiationStatus
  settlement: SettlementStatus
  release_token?: ReleaseToken
  dataset_metrics: DatasetMetrics
  enclave_signature?: string
}
