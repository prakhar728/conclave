import type {
  AttestationResponse,
  DisplayMap,
  HealthResponse,
  InitRequest,
  InitResponse,
  NoveltyResult,
  ProcurementResult,
  ReleaseToken,
  SkillCard,
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

  // --- Procurement ---
  submitDataset: async (token: string, submission: SupplierSubmission): Promise<SubmitResponse> => {
    await delay(800)
    return {
      submission_id: `proc_${Math.random().toString(36).slice(2, 9)}`,
      status: "received_pending",
      submissions_count: 1,
    }
  },

  getProcurementResult: async (
    token: string,
    submission_id: string,
  ): Promise<ProcurementResult> => {
    await delay(400)
    const r = MOCK_PROCUREMENT_RESULTS.find((r) => r.submission_id === submission_id)
    return r ?? MOCK_PROCUREMENT_RESULTS[0]!
  },

  getProcurementResults: async (token: string): Promise<{ results: ProcurementResult[] }> => {
    await delay(400)
    return { results: MOCK_PROCUREMENT_RESULTS }
  },

  acceptDeal: async (token: string, submission_id: string): Promise<{ status: string }> => {
    await delay(300)
    return { status: "accepted" }
  },

  rejectDeal: async (token: string, submission_id: string): Promise<{ status: string }> => {
    await delay(300)
    return { status: "rejected" }
  },

  requestNegotiation: async (
    token: string,
    submission_id: string,
    revised_value: number,
  ): Promise<{ status: string }> => {
    await delay(300)
    return { status: "negotiation_requested" }
  },

  submitRenegotiation: async (
    token: string,
    submission_id: string,
    revised_value: number,
  ): Promise<{ status: string }> => {
    await delay(300)
    return { status: "renegotiation_submitted" }
  },

  getReleaseToken: async (token: string, submission_id: string): Promise<ReleaseToken> => {
    await delay(300)
    return {
      token: `tok_${Math.random().toString(36).slice(2, 18)}`,
      issued_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    }
  },
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}
