import type {
  AttestationResponse,
  BackendProcurementResult,
  DatasetMetrics,
  DisplayMap,
  HardConstraintResult,
  HealthResponse,
  InitRequest,
  InitResponse,
  MilestoneScore,
  NegotiationState,
  NegotiationStatus,
  NoveltyResult,
  ProcurementResult,
  ReleaseToken,
  SettlementState,
  SkillCard,
  SubmissionMeta,
  SubmitResponse,
  SupplierSubmission,
} from "./types"

const MOCK = false
const TEE_URL = process.env.NEXT_PUBLIC_TEE_URL ?? "http://localhost:8000"

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const HACKATHON_NOVELTY_DISPLAY: DisplayMap = {
  novelty_score:   { type: "gauge",       label: "Novelty",            min: 0, max: 1 },
  percentile:      { type: "percentile",  label: "Percentile" },
  cluster:         { type: "badge",       label: "Cluster" },
  status:          { type: "badge",       label: "Status" },
  analysis_depth:  { type: "badge",       label: "Depth" },
  duplicate_of:    { type: "text",        label: "Duplicate Of" },
  criteria_scores: { type: "score_table", label: "Criteria Breakdown" },
}

const MOCK_SKILLS: SkillCard[] = [
  {
    name: "hackathon_novelty",
    description:
      "Scores hackathon submissions for novelty against each other. Uses embeddings + LangGraph agent to produce novelty scores, percentile rankings, and per-criteria evaluations.",
    version: "0.1.0",
    input_schema: {
      properties: {
        submission_id: { type: "string" },
        idea_text: { type: "string" },
        repo_summary: { type: "string" },
        deck_text: { type: "string" },
      },
    },
    output_keys: [
      "submission_id",
      "novelty_score",
      "aligned",
      "criteria_scores",
      "status",
      "analysis_depth",
      "duplicate_of",
    ],
    config: { min_submissions: 5 },
    trigger_modes: [
      { mode: "threshold", description: "Auto-triggers at submission threshold" },
      { mode: "manual", description: "Operator manually triggers analysis" },
    ],
    roles: {
      operator: { can_trigger: true, can_view_all: true },
      participant: { can_view_own: true },
    },
    setup_prompt:
      "Configure your hackathon evaluation criteria, scoring weights, and judging guidelines.",
    user_display: HACKATHON_NOVELTY_DISPLAY,
  },
  {
    name: "dataset_audit",
    description:
      "Audits datasets for quality issues — null rates, distribution anomalies, schema violations — without exposing raw rows.",
    version: "0.1.0",
    input_schema: { properties: { submission_id: { type: "string" } } },
    output_keys: ["submission_id", "quality_score", "null_rate", "anomaly_count"],
    config: { min_submissions: 1 },
    trigger_modes: [{ mode: "instant" }],
    roles: {
      operator: { can_trigger: true, can_view_all: true },
      participant: { can_view_own: true },
    },
    setup_prompt: "Upload your dataset schema and define the quality thresholds.",
    user_display: {
      quality_score:  { type: "gauge",  label: "Quality Score", min: 0, max: 1 },
      null_rate:      { type: "gauge",  label: "Null Rate",     min: 0, max: 1 },
      anomaly_count:  { type: "text",   label: "Anomalies" },
    },
  },
]

const MOCK_ATTESTATION: AttestationResponse = {
  quote:
    "0x04000200810000001f00210000000000000000000000000000000000000000000000000000000000000000000000000000000000000015000000e00000000000000096126d6b7d5a96cd96d2e1e7e17e2a21c09b0d2d8cbb30c2e1e4",
  verify_url: "https://cloud-api.phala.network/api/v1/attestations/verify",
}

const MOCK_PROCUREMENT_RESULTS: ProcurementResult[] = [
  {
    submission_id: "proc_001",
    hard_constraints: [
      { name: "Required columns present", passed: true },
      { name: "Min row count (1,000)", passed: true },
      { name: "Max null rate (5%)", passed: false, detail: "Null rate: 7.2%" },
      { name: "No forbidden columns", passed: true },
    ],
    milestones: [
      { name: "Data completeness", weight: 0.3, score: 0.85, passed: true },
      { name: "Schema compliance", weight: 0.25, score: 1.0, passed: true },
      { name: "Distribution quality", weight: 0.25, score: 0.72, passed: true },
      { name: "Claim verification", weight: 0.2, score: 0.6, passed: true },
    ],
    claim_results: {
      "10,000+ rows": true,
      "No PII columns": true,
      "Label rate > 80%": false,
    },
    partial_score: 0.79,
    proposed_payment: 7900,
    negotiation: { state: "none", used: false },
    settlement: { state: "none" },
    dataset_metrics: {
      row_count: 12500,
      null_rate: 0.072,
      duplicate_rate: 0.01,
      column_count: 14,
      columns_present: ["id", "label", "feature_1", "feature_2"],
      columns_missing: [],
    },
    enclave_signature: "0xdeadbeef5678...",
  },
]

const MOCK_RESULTS: NoveltyResult[] = [
  {
    submission_id: "sub_001",
    novelty_score: 0.84,
    aligned: true,
    criteria_scores: { originality: 8.5, feasibility: 7.2, impact: 9.0 },
    status: "analyzed",
    analysis_depth: "full",
    duplicate_of: null,
    enclave_signature: "0xdeadbeef1234...",
    attestation_quote: MOCK_ATTESTATION.quote,
  },
  {
    submission_id: "sub_002",
    novelty_score: 0.61,
    aligned: true,
    criteria_scores: { originality: 6.0, feasibility: 8.5, impact: 5.5 },
    status: "analyzed",
    analysis_depth: "full",
    duplicate_of: null,
  },
  {
    submission_id: "sub_003",
    novelty_score: 0.12,
    aligned: true,
    criteria_scores: { originality: 2.0, feasibility: 6.0, impact: 3.0 },
    status: "duplicate",
    analysis_depth: "flagged",
    duplicate_of: "sub_001",
  },
]

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

function authHeaders(token: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Instance-Token": token,
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function post<T>(path: string, body: unknown, token?: string): Promise<T> {
  const res = await fetch(`${TEE_URL}${path}`, {
    method: "POST",
    headers: token ? authHeaders(token) : { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(res.status, `${path} failed: ${res.status}`)
  return res.json()
}

async function get<T>(path: string, token?: string): Promise<T> {
  const res = await fetch(`${TEE_URL}${path}`, {
    headers: token ? authHeaders(token) : {},
  })
  if (!res.ok) throw new ApiError(res.status, `${path} failed: ${res.status}`)
  return res.json()
}

async function postForm<T>(path: string, form: FormData, token: string): Promise<T> {
  const res = await fetch(`${TEE_URL}${path}`, {
    method: "POST",
    headers: { "X-Instance-Token": token },
    body: form,
  })
  if (!res.ok) throw new ApiError(res.status, `${path} failed: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Backend → frontend result adapter
// ---------------------------------------------------------------------------

function adaptBackendResult(raw: BackendProcurementResult): ProcurementResult {
  // Hard constraints: backend gives a single bool; build a minimal array
  const hard_constraints: HardConstraintResult[] =
    raw.hard_constraints_pass !== undefined
      ? [
          {
            name: "Hard constraints",
            passed: raw.hard_constraints_pass,
            detail:
              !raw.hard_constraints_pass && raw.notes.length > 0
                ? raw.notes.join("; ")
                : undefined,
          },
        ]
      : []

  // Milestones: map component_scores from backend (buyer-only field)
  const COMPONENT_LABELS: Record<string, string> = {
    schema:         "Schema match",
    coverage:       "Row coverage",
    null:           "Null rate",
    duplicate:      "Duplicate rate",
    label:          "Label balance",
    risk:           "Risk / forbidden cols",
    claim_veracity: "Claim veracity",
  }
  const COMPONENT_WEIGHTS: Record<string, number> = {
    schema: 0.15, coverage: 0.15, null: 0.20,
    duplicate: 0.15, label: 0.10, risk: 0.15, claim_veracity: 0.10,
  }
  const milestones: MilestoneScore[] = raw.component_scores
    ? Object.entries(raw.component_scores).map(([key, score]) => ({
        name: COMPONENT_LABELS[key] ?? key,
        weight: COMPONENT_WEIGHTS[key] ?? 0,
        score,
        passed: score >= 0.5,
      }))
    : []

  // Claim results: map from claim_verification dict (agent layer)
  const claim_results: Record<string, boolean> = {}
  const cv = raw.claim_verification
  if (cv && typeof cv === "object") {
    for (const [k, v] of Object.entries(cv)) {
      claim_results[k] = typeof v === "boolean" ? v : Boolean(v)
    }
  }

  // Negotiation state: derive from response fields + settlement_status
  const { buyer_response, supplier_response, renegotiation_used, settlement_status } = raw
  let negState: NegotiationState = "none"
  if (settlement_status === "authorized") {
    negState = "accepted"
  } else if (settlement_status === "rejected") {
    // Covers both enclave auto-rejection (no responses) and user-initiated rejection
    negState = "rejected"
  } else if (settlement_status === "awaiting_counterparty") {
    // One party responded, the other hasn't — identify who needs to act next
    if (buyer_response && !supplier_response) {
      negState = "requested_by_buyer"   // buyer went; seller's turn
    } else if (supplier_response && !buyer_response) {
      negState = "requested_by_seller"  // seller went; buyer's turn
    } else {
      negState = "awaiting_counterparty"
    }
  } else if (renegotiation_used) {
    negState = "renegotiation_submitted"
  }

  const negotiation: NegotiationStatus = {
    state: negState,
    used: renegotiation_used,
    revised_budget: raw.revised_budget ?? undefined,
    revised_reserve: raw.revised_reserve ?? undefined,
  }

  // Settlement state
  let settlState: SettlementState = "none"
  if (settlement_status === "authorized") settlState = "authorized"
  else if (settlement_status === "rejected") settlState = "failed"
  else if (
    settlement_status === "pending_approval" ||
    settlement_status === "awaiting_counterparty" ||
    settlement_status === "renegotiating"
  )
    settlState = "pending"

  // Release token: backend returns a plain string
  let release_token: ReleaseToken | undefined
  if (raw.release_token) {
    release_token = { token: raw.release_token, issued_at: new Date().toISOString() }
  }

  // Dataset metrics: not exposed by backend; use empty stub
  const dataset_metrics: DatasetMetrics = {
    row_count: 0,
    null_rate: 0,
    duplicate_rate: 0,
    column_count: 0,
    columns_present: [],
    columns_missing: [],
  }

  return {
    submission_id: raw.submission_id,
    hard_constraints,
    milestones,
    claim_results,
    partial_score: raw.quality_score ?? 0,
    proposed_payment: raw.proposed_payment,
    negotiation,
    settlement: {
      state: settlState,
      amount: settlState === "authorized" ? raw.proposed_payment : undefined,
    },
    release_token,
    dataset_metrics,
  }
}

export const api = {
  // --- Public ---
  checkInstance: async (instance_id: string): Promise<{ skill_name: string; triggered: boolean; submissions: number; threshold: number }> => {
    return get(`/instances/${instance_id}`)
  },

  health: async (): Promise<HealthResponse> => {
    if (MOCK)
      return { status: "ok", instances: 3, submissions: 12, skills: ["hackathon_novelty"] }
    return get("/health")
  },

  getAttestation: async (): Promise<AttestationResponse> => {
    if (MOCK) {
      await delay(1200)
      return MOCK_ATTESTATION
    }
    return get("/attestation")
  },

  getSkills: async (): Promise<{ skills: SkillCard[] }> => {
    if (MOCK) return { skills: MOCK_SKILLS }
    return get("/skills")
  },

  getSkill: async (name: string): Promise<SkillCard> => {
    if (MOCK) {
      const skill = MOCK_SKILLS.find((s) => s.name === name)
      if (!skill) throw new Error(`Skill ${name} not found`)
      return skill
    }
    return get(`/skills/${name}`)
  },

  // --- Operator setup ---
  initInstance: async (body: InitRequest): Promise<InitResponse> => {
    if (MOCK) {
      await delay(800)
      if (!body.instance_id) {
        return {
          instance_id: `inst_${Math.random().toString(36).slice(2, 9)}`,
          status: "configuring",
          message:
            "Hi! Tell me about the hackathon you're running — what kind of ideas will participants submit, and what are the most important qualities you want to evaluate?",
        }
      }
      // Simulate one more turn then ready
      const isReady = body.message.toLowerCase().includes("yes") ||
        body.message.toLowerCase().includes("good") ||
        body.message.toLowerCase().includes("perfect") ||
        body.message.toLowerCase().includes("ok") ||
        body.message.toLowerCase().includes("confirm")
      if (isReady) {
        return {
          instance_id: body.instance_id,
          status: "ready",
          message: "All set! Your instance is configured and ready to accept submissions.",
          admin_token: `adm_${Math.random().toString(36).slice(2, 18)}`,
          user_token: `usr_${Math.random().toString(36).slice(2, 18)}`,
        }
      }
      return {
        instance_id: body.instance_id,
        status: "configuring",
        message:
          "Got it — I've noted originality (40%), feasibility (30%), and impact (30%) as your criteria. Should the threshold be 5 submissions before analysis runs? And do you have any specific judging guidelines for the AI?",
      }
    }
    return post("/init", body)
  },

  // --- GitHub ---
  fetchRepo: async (token: string, repo_url: string): Promise<{ repo_summary: string }> => {
    if (MOCK) {
      await delay(1500)
      return {
        repo_summary: `Repository: example/my-project\n\nREADME:\n# My Hackathon Project\n\nAn innovative platform using TEE technology to enable secure multi-party computation...\n\nFiles:\nsrc/main.py\nsrc/api.py\nDockerfile\nrequirements.txt`,
      }
    }
    return post("/fetch-repo", { repo_url }, token)
  },

  // --- Auth ---
  sendOtp: async (email: string, instance_id: string): Promise<void> => {
    await post("/auth/send-otp", { email, instance_id })
  },

  verifyOtp: async (email: string, token: string, instance_id: string): Promise<{ user_token: string }> => {
    return post("/auth/verify-otp", { email, token, instance_id })
  },

  verifyToken: async (access_token: string, instance_id: string): Promise<{ user_token: string }> => {
    return post("/auth/verify-token", { access_token, instance_id })
  },

  // --- Participant ---
  getMySubmissions: async (token: string): Promise<{ submission_ids: string[] }> => {
    return get("/my-submissions", token)
  },

  submit: async (token: string, submission: Record<string, unknown>): Promise<SubmitResponse> => {
    if (MOCK) {
      await delay(600)
      return {
        submission_id: `mock-${Math.random().toString(36).slice(2, 9)}`,
        status: "received_pending",
        submissions_count: 3,
        threshold: 5,
      }
    }
    return post("/submit", submission, token)
  },

  getOwnResult: async (token: string, submission_id: string): Promise<NoveltyResult> => {
    if (MOCK) {
      await delay(400)
      const r = MOCK_RESULTS.find((r) => r.submission_id === submission_id)
      if (!r) throw new Error("Result not found")
      return r
    }
    return get(`/results/${submission_id}`, token)
  },

  // --- Token resolution ---
  resolveToken: async (token: string): Promise<{ instance_id: string; role: string }> => {
    return get("/me", token)
  },

  // --- Operator ---
  trigger: async (token: string): Promise<{ status: string; results_count: number }> => {
    if (MOCK) {
      await delay(2000)
      return { status: "complete", results_count: 5 }
    }
    return post("/trigger", {}, token)
  },

  getAllResults: async (token: string): Promise<{ results: NoveltyResult[] }> => {
    if (MOCK) {
      await delay(400)
      return { results: MOCK_RESULTS }
    }
    return get("/results", token)
  },

  getSubmissions: async (token: string): Promise<{ submissions: SubmissionMeta[] }> => {
    if (MOCK) {
      await delay(300)
      return { submissions: [] }
    }
    return get("/submissions", token)
  },

  // --- Procurement ---
  submitDataset: async (
    token: string,
    submission: SupplierSubmission,
    file?: File,
    metadataFile?: File | null,
  ): Promise<SubmitResponse> => {
    // Step 1: upload the CSV file + metadata JSON
    if (!file) throw new ApiError(422, "A CSV file is required for dataset submission")
    const form = new FormData()
    form.append("csv_file", file)

    if (metadataFile) {
      // Use the file the seller uploaded directly
      form.append("metadata_file", metadataFile, metadataFile.name)
    } else {
      // Fall back: build metadata.json from the form fields
      const sellerClaimsObj: Record<string, string | number> = {}
      for (const c of submission.seller_claims ?? []) {
        sellerClaimsObj[c.name] = c.value
      }
      const metadataPayload: Record<string, unknown> = { seller_claims: sellerClaimsObj }
      if (submission.note) metadataPayload.note = submission.note
      if (submission.dataset_reference) metadataPayload.dataset_reference = submission.dataset_reference
      form.append(
        "metadata_file",
        new Blob([JSON.stringify(metadataPayload)], { type: "application/json" }),
        "metadata.json",
      )
    }

    const { dataset_id } = await postForm<{ dataset_id: string }>("/upload", form, token)

    // Step 2: submit with the returned dataset_id
    const submission_id = `proc_${Math.random().toString(36).slice(2, 14)}`
    return post(
      "/submit",
      {
        submission_id,
        dataset_id,
        dataset_name: submission.dataset_name,
        reserve_price: submission.reserve_price,
      },
      token,
    )
  },

  getProcurementResult: async (
    token: string,
    submission_id: string,
  ): Promise<ProcurementResult> => {
    const raw = await get<BackendProcurementResult>(`/results/${submission_id}`, token)
    return adaptBackendResult(raw)
  },

  getProcurementResults: async (token: string): Promise<{ results: ProcurementResult[] }> => {
    const { results } = await get<{ results: BackendProcurementResult[] }>("/results", token)
    return { results: results.map(adaptBackendResult) }
  },

  acceptDeal: async (token: string, submission_id: string): Promise<{ settlement_status: string }> => {
    return post("/respond", { submission_id, action: "accept" }, token)
  },

  rejectDeal: async (token: string, submission_id: string): Promise<{ settlement_status: string }> => {
    return post("/respond", { submission_id, action: "reject" }, token)
  },

  requestNegotiation: async (
    token: string,
    submission_id: string,
    revised_value: number,
  ): Promise<{ settlement_status: string }> => {
    return post("/respond", { submission_id, action: "renegotiate", revised_value }, token)
  },

  submitRenegotiation: async (
    token: string,
    submission_id: string,
    revised_value: number,
  ): Promise<{ settlement_status: string }> => {
    return post("/respond", { submission_id, action: "renegotiate", revised_value }, token)
  },

  getReleaseToken: async (token: string, submission_id: string): Promise<ReleaseToken> => {
    const raw = await get<BackendProcurementResult>(`/results/${submission_id}`, token)
    if (!raw.release_token) throw new ApiError(404, "No release token available yet")
    return { token: raw.release_token, issued_at: new Date().toISOString() }
  },
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}
