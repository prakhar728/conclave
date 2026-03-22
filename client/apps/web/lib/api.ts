import type {
  AttestationResponse,
  HealthResponse,
  InitRequest,
  InitResponse,
  NoveltyResult,
  SkillCard,
  SubmitResponse,
} from "./types"

const MOCK = false
const TEE_URL = process.env.NEXT_PUBLIC_TEE_URL ?? "http://localhost:8000"

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

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
  },
]

const MOCK_ATTESTATION: AttestationResponse = {
  quote:
    "0x04000200810000001f00210000000000000000000000000000000000000000000000000000000000000000000000000000000000000015000000e00000000000000096126d6b7d5a96cd96d2e1e7e17e2a21c09b0d2d8cbb30c2e1e4",
  verify_url: "https://cloud-api.phala.network/api/v1/attestations/verify",
}

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

async function post<T>(path: string, body: unknown, token?: string): Promise<T> {
  const res = await fetch(`${TEE_URL}${path}`, {
    method: "POST",
    headers: token ? authHeaders(token) : { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json()
}

async function get<T>(path: string, token?: string): Promise<T> {
  const res = await fetch(`${TEE_URL}${path}`, {
    headers: token ? authHeaders(token) : {},
  })
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  // --- Public ---
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

  // --- Participant ---
  submit: async (token: string, submission: Record<string, unknown>): Promise<SubmitResponse> => {
    if (MOCK) {
      await delay(600)
      return {
        submission_id: submission.submission_id as string,
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
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}
