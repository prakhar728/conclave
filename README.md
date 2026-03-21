# Conclave

Multi-party TEE platform where sensitive data goes in and only derived outputs come out. Built for scenarios where multiple parties need AI-generated insights from each other's data without anyone — including the platform operator — seeing the raw inputs.

Each use case is a **skill**: a self-contained analysis pipeline running inside a Trusted Execution Environment. The platform is a skill gallery — anyone can build a skill for their domain and the TEE guarantees that raw submissions never leave the enclave. Only derived results do.

---

## The Problem It Solves

Consider a hackathon where 200 teams submit ideas. The organizer wants novelty scores and duplicate detection across all submissions. But participants don't want their unpublished ideas seen by other participants or even by the organizer before judging. Standard solutions require trusting a central party. Conclave eliminates that trust requirement by running the analysis inside a hardware-attested enclave.

The same pattern applies to:
- Competitive intelligence aggregation across companies
- Sensitive dataset auditing across organizations
- Any scenario where insights from combined data are useful but raw data is private

---

## How It Works

```
Operator configures a skill instance (POST /init, multi-turn LLM conversation)
  ↓
Participants register unique tokens (POST /register) and submit data (POST /submit)
  ↓
Pipeline auto-triggers inside the TEE once enough submissions arrive
  ↓
Each participant sees only their own result. Operator sees aggregated results.
Raw inputs never leave the enclave.
```

Two roles:
- **Operator (admin)** — configures the instance, triggers evaluation, views all results
- **Participant (user)** — registers, submits data, views only their own result

---

## What Is Implemented

### Core runtime
- `POST /init` — multi-turn LLM onboarding loop for operators. Skill owns the conversation; API issues tokens when the skill says it's ready.
- `POST /register` — per-user token issuance. Each participant gets a unique token. The TEE tracks which submission IDs belong to which token.
- `POST /submit` — submission ingestion with auto-trigger at configurable threshold. Re-triggers on every subsequent submission so all scores stay current.
- `POST /trigger` — admin manual trigger (bypasses threshold).
- `GET /results` — all results, admin only.
- `GET /results/{id}` — single result with ownership enforcement: user tokens can only retrieve submission IDs they submitted. Returns 403 otherwise.
- `GET /skills`, `GET /skills/{name}` — rich skill metadata from `SkillCard`.
- `GET /attestation` — TDX attestation quote from the dstack agent, verifiable via Phala's attestation API.
- `POST /fetch-repo` — fetches a GitHub repo summary inside the TEE (public repos or private via GitHub App).

### Skill: `hackathon_novelty` (fully implemented)
The reference skill. Accepts idea text, optional repo summary, optional pitch deck content. Outputs novelty score, criteria scores, percentile rank, and cluster assignment.

Three-layer pipeline:
1. **Deterministic** — sentence embeddings, cosine similarity matrix, novelty scoring, KMeans clustering. No LLM, fully reproducible.
2. **Agent** — LangGraph graph that triages each submission (duplicate / quick / deep analysis path) and runs LLM evaluation with constrained tool access.
3. **Guardrails** — strips keys not on the allowed whitelist, clamps numeric values to valid ranges, detects raw input leakage in LLM outputs before results leave the skill.

Operator configures via conversation: criteria weights, evaluation guidelines, submission threshold. The init handler validates that weights sum to 1.0 and threshold is numeric before accepting the configuration.

### Skill: `dataset_audit` (stub)
Package exists with the right structure. Not implemented. Intended for cross-org dataset quality auditing.

### TEE infrastructure
- `infra/enclave.py` — dstack agent integration for TDX attestation quotes and hardware-bound result signing. Gracefully stubs outside the enclave for local dev.
- `infra/github_app.py` — GitHub App integration for fetching private repo content inside the TEE.
- Deployed on Phala Network CVM (Confidential VM). Attestation verifiable at `https://cloud-api.phala.network/api/v1/attestations/verify`.

### Test coverage
54 tests, all passing without API keys (LLM calls mocked). Covers: operator init loop, auto-trigger, manual trigger, role enforcement, result ownership isolation, missing submission IDs, bad config validation, re-trigger on N+1 submission.

---

## API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/init` | None | Operator onboarding loop. Call until `status="ready"`, receive `admin_token`. |
| `POST` | `/auth/send-otp` | None | Step 1 of participant login. Sends OTP to email via Supabase. |
| `POST` | `/auth/verify-otp` | None | Step 2 of participant login. Verifies OTP, issues internal `user_token`. Idempotent per identity per instance. |
| `POST` | `/register` | None | Dev fallback — issue a user token without Supabase auth. Only works when Supabase is not configured. |
| `POST` | `/submit` | User or Admin | Submit data. Auto-triggers pipeline at threshold. |
| `POST` | `/trigger` | Admin | Manual pipeline trigger. |
| `GET` | `/results` | Admin | All results for the instance. |
| `GET` | `/results/{id}` | User or Admin | Single result. Users see only submissions they own; returns 403 otherwise. |
| `GET` | `/skills` | None | Metadata for all registered skills. |
| `GET` | `/skills/{name}` | None | Metadata for one skill. |
| `GET` | `/attestation` | None | TDX attestation quote for this enclave instance. |
| `POST` | `/fetch-repo` | Any | Fetch a GitHub repo summary inside the TEE. |
| `GET` | `/health` | None | Status check. |

All authenticated requests send the token as `X-Instance-Token` header.

---

## Authentication Model

**Current implementation:** Supabase OTP email auth + internal token tracking.

1. Operator calls `/init` → receives `admin_token`
2. Operator shares `instance_id` with participants
3. Participant calls `POST /auth/send-otp` with `{email, instance_id}` → Supabase sends a 6-digit OTP
4. Participant calls `POST /auth/verify-otp` with `{email, token, instance_id}` → TEE verifies OTP with Supabase, validates the returned JWT **locally** using `SUPABASE_JWT_SECRET` (HS256, no extra network call), issues an internal `user_token`
5. Participant submits with their `user_token`. The TEE records `token → submission_id` ownership.
6. `GET /results/{id}` enforces ownership: a token can only read results for submissions it made. Returns 403 otherwise.
7. Re-registering with the same email for the same instance is idempotent — returns the existing token.

**Dev fallback:** `POST /register` (no Supabase required) — works when `CONCLAVE_SUPABASE_URL` is not set. Used in all tests.

**Required env vars:**
```
CONCLAVE_SUPABASE_URL=https://<project>.supabase.co
CONCLAVE_SUPABASE_ANON_KEY=<anon / public key>
```
JWT validation uses Supabase's JWKS endpoint (ES256 / ECC P-256) — public keys are fetched once on first use and cached. No shared secret needed.

**Privacy tradeoff of Supabase auth:** Supabase sees every auth event — who authenticated, when. If the threat model requires that no external party can link a person to their submission, Supabase breaks that. Alternatives considered:

- **Operator-issued single-use registration codes** — operator pre-generates N codes at init time, distributes out-of-band. TEE validates codes without ever seeing identity. Weakness: operator knows who got which code.
- **Semaphore (ZK group membership)** — participants prove "I am in the allowed group" with a zero-knowledge proof, revealing nothing about which member they are. Neither the operator nor any external service can link a proof to a person. Non-trivial to implement; requires participants to have compatible tooling.
- **World ID** — ZK proof of unique personhood via iris scan. Strongest uniqueness + anonymity guarantee. Hard dependency on World ID hardware and participant enrollment.

For the current use case (hackathon), Supabase OTP is the right call — the operator already knows who the participants are, and the implementation complexity of ZK alternatives isn't justified. The ZK path (Semaphore) is the right answer if the threat model ever requires that the operator cannot link submissions to identities.

---

## Project Structure

```
main.py                              # FastAPI app entry point
api/routes.py                        # REST endpoints — transport and state only, no skill logic
core/
├── models.py                        # Shared data models (Submission, OperatorConfig, SkillResponse, etc.)
├── skill_card.py                    # SkillCard — the contract every skill declares
└── guardrails.py                    # LeakageDetector, OutputFilterBase (abstract)
skills/
├── router.py                        # SkillRouter — registers cards, dispatches invocations
├── hackathon_novelty/               # Fully implemented reference skill
│   ├── __init__.py                  # skill_card + run_skill entry point
│   ├── models.py                    # HackathonSubmission, NoveltyResult
│   ├── deterministic.py             # Layer 1: embeddings, similarity, clustering
│   ├── agent.py                     # Layer 2: LangGraph multi-node graph
│   ├── tools.py                     # Triage and analysis tools exposed to the agent
│   ├── guardrails.py                # Layer 3: output filter
│   ├── init.py                      # Operator onboarding conversation handler
│   └── config.py                    # LLM and embedding model config for this skill
└── dataset_audit/                   # Stub — structure only, not implemented
infra/
├── enclave.py                       # dstack agent: attestation quotes + result signing
└── github_app.py                    # GitHub App integration for private repo access
tests/
└── test_e2e.py                      # 54 tests, all mocked (no API keys needed)
config.py                            # LLM provider selection (OpenAI / Anthropic / Google)
docker-compose.yml                   # Local dev stack
Dockerfile                           # Production image for Phala CVM deployment
docs/architecture.md                 # Architecture deep-dive with Mermaid diagrams
```

---

## Quickstart

```bash
cp .env.example .env       # add your LLM API key (OPENAI_API_KEY or ANTHROPIC_API_KEY)
pip install -r requirements.txt
uvicorn main:app --reload  # http://localhost:8000
```

Or with Docker:

```bash
docker-compose up
```

---

## Running Tests

```bash
pytest tests/ -v           # 54 tests, no API keys needed
```

CI runs on every push via GitHub Actions.

---

## Adding a New Skill

1. Create `skills/<name>/` with `models.py`, `deterministic.py`, `agent.py`, `guardrails.py`, `init.py`, `config.py`, `__init__.py`
2. Define a `<Name>Submission` extending `core.models.Submission`
3. Implement the three layers: deterministic → agent → guardrails
4. Implement an `init_handler` for operator onboarding (or omit for instant-start skills)
5. Export a `skill_card` from `__init__.py`
6. Add one import line in `api/routes.py:register_skills()`

No changes needed to `core/`, `api/`, or the TEE infrastructure.

---

## Known Limitations

- **State is in-memory only.** No persistence layer. Instance state is lost on restart.
- **Single-worker deployment assumed.** The submission threshold check is not atomic. Safe under uvicorn's default single-worker mode. Would need per-instance locking if changed to multi-worker.
- **`dataset_audit` is a stub.** The package structure exists but the pipeline is not implemented.
- **Frontend not wired.** The `client/` Next.js app is a scaffold. Not connected to the backend.
- **`/register` (dev fallback) is open to anyone** who knows the `instance_id`. In production, use `/auth/send-otp` + `/auth/verify-otp` with Supabase configured.
- **CORS is permissive (`*`).** Appropriate for enclave deployment where the client origin isn't fixed, but worth reviewing per deployment.
