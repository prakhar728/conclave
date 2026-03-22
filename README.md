# Conclave

TEE platform for confidential protocols, with a current focus on confidential dataset negotiation and procurement based on the core mechanism from the NDAI Agreements paper: conditional disclosure of an information good inside a remotely attested enclave.

Conclave is built for scenarios where multiple parties need AI-mediated evaluation, negotiation, or decision-making over sensitive data without anyone — including the platform operator — seeing the raw inputs outside the enclave.

Each use case is a confidential **protocol**: a domain-specific workflow running inside a Trusted Execution Environment. Internally, the codebase still models these as `skills`, but the product is better thought of as a platform for confidential protocols and trust-sensitive workflows. The TEE guarantees that raw submissions never leave the enclave. Only policy-approved outputs do.

---

## The Problem It Solves

The flagship use case for Conclave is confidential dataset negotiation.

Today, dataset procurement is structurally broken:

- buyers cannot judge whether a dataset is worth buying without seeing too much of it
- sellers cannot safely reveal enough to prove value without risking unpaid extraction
- sampling, previews, and manual NDAs leak value and still rely on trust
- as a result, many potentially valuable trades never happen

This is a concrete instance of the central problem from the NDAI Agreements paper: the disclosure paradox.

- a seller has a valuable information good
- a buyer needs disclosure to evaluate it
- disclosure creates expropriation risk
- therefore many economically valuable trades never happen

In ordinary software, the seller has to trust the buyer, the marketplace, or the operator not to misuse the information after seeing it. That trust assumption is exactly what breaks down.

Conclave is aimed at replacing that trust assumption with enclave-enforced protocol logic for dataset procurement:

- the buyer submits dataset requirements, milestone weights, and max budget
- the seller submits a dataset, claims, and a reserve price
- the enclave runs deterministic checks and judge-gated agentic verification privately
- the buyer receives only bounded evaluation outputs before agreement
- proposed payment is computed inside the enclave from buyer-defined rules
- if both sides accept, the buyer receives a download token and the seller receives settlement authorization
- if the deal fails, the raw dataset never leaves the secure environment

This is the current product thesis: Conclave should feel like a confidential deal room for information goods, not a generic TEE analytics demo.

The current implementation started with a hackathon novelty workflow because it was a simple reference protocol for confidential evaluation. But the main product direction now is dataset procurement first, with other NDAI-style bilateral workflows following from the same runtime.

Other protocol categories the same runtime can support:

- private diligence and memo review
- salary or compensation negotiation
- competitive intelligence aggregation
- cross-org dataset auditing
- any workflow where useful decisions require sensitive inputs but raw disclosure is unacceptable

## How It Works

```
Buyer configures a procurement instance (POST /init, multi-turn setup)
  ↓
Seller uploads a confidential dataset and reserve price (POST /submit)
  ↓
The enclave evaluates the dataset privately using deterministic checks and judge-gated agentic verification
  ↓
Both sides receive bounded evaluation outputs and a proposed payment
  ↓
Either side can accept, reject, or use one renegotiation round
  ↓
On success, the buyer receives a download token and the seller receives settlement authorization
On failure, the raw dataset never leaves the enclave
```

Today the shared runtime supports two generic roles:
- **Operator (admin)** — configures the instance, triggers evaluation, views all results
- **Participant (user)** — registers, submits data, views only their own result

For the dataset procurement protocol, these generic roles map to more specific economic roles such as **buyer** and **seller**. That protocol-specific role model is part of the current roadmap.

Some protocols will later introduce different role semantics such as **buyer** and **seller**, but the current shared runtime still uses the generic admin/user token model.

---

## What Is Implemented

### Core runtime
- `POST /init` — multi-turn LLM onboarding loop for operators. The protocol package owns the conversation; API issues tokens when it says setup is ready.
- `POST /register` — per-user token issuance. Each participant gets a unique token. The TEE tracks which submission IDs belong to which token.
- `POST /submit` — submission ingestion with auto-trigger at configurable threshold. Re-triggers on every subsequent submission so all scores stay current.
- `POST /trigger` — admin manual trigger (bypasses threshold).
- `GET /results` — all results, admin only.
- `GET /results/{id}` — single result with ownership enforcement: user tokens can only retrieve submission IDs they submitted. Returns 403 otherwise.
- `GET /skills`, `GET /skills/{name}` — rich protocol metadata from `SkillCard` (internal abstraction name retained for now).
- `GET /attestation` — TDX attestation quote from the dstack agent, verifiable via Phala's attestation API.
- `POST /fetch-repo` — fetches a GitHub repo summary inside the TEE (public repos or private via GitHub App).

### Main planned protocol: confidential data procurement
The primary application direction for Conclave is a bilateral buyer/seller workflow for dataset procurement inside the TEE:

- buyer defines procurement policy, milestone weights, hard constraints, and max budget
- seller uploads a dataset, claims, and reserve price
- enclave evaluates deterministic and agentic checks privately
- enclave computes a partial weighted score and proposed payment
- both sides can accept, reject, or use one renegotiation round
- on successful agreement, the buyer receives a download token and the seller receives simulated settlement authorization

Planned MVP mechanics:

- CSV-first ingestion
- deterministic metrics for rows, columns, duplicates, nulls, labels, and forbidden fields
- judge-gated agentic claim verification
- buyer-defined weighted partial scoring
- proposed payment derived from buyer budget and enclave score
- mocked settlement stored as DB/session state only
- no real payment rails in v1

This protocol is currently in planning and UI-prototyping stage. It is not implemented in the backend yet.

Relevant planning docs:

- `plans/confidential_data_procurement.md`
- `plans/ui_changes.md`

### Protocol: `hackathon_novelty` (fully implemented reference)
This is the currently implemented reference protocol in the backend. It accepts idea text, optional repo summary, optional pitch deck content, and outputs novelty score, criteria scores, percentile rank, and cluster assignment.

Three-layer pipeline:
1. **Deterministic** — sentence embeddings, cosine similarity matrix, novelty scoring, KMeans clustering. No LLM, fully reproducible.
2. **Agent** — LangGraph graph that triages each submission (duplicate / quick / deep analysis path) and runs LLM evaluation with constrained tool access.
3. **Guardrails** — strips keys not on the allowed whitelist, clamps numeric values to valid ranges, detects raw input leakage in LLM outputs before results leave the protocol.

Operator configures via conversation: criteria weights, evaluation guidelines, submission threshold. The init handler validates that weights sum to 1.0 and threshold is numeric before accepting the configuration.

### Protocol: `dataset_audit` (stub)
Package exists with the right structure. Not implemented. Intended for cross-org dataset quality auditing.

### Research grounding: NDAI Agreements

The current product direction is based on the paper:

- *NDAI Agreements* ([arXiv:2502.07924](https://arxiv.org/abs/2502.07924))

The paper's key idea is that TEEs plus AI agents can mitigate the classic disclosure hold-up problem by making disclosure conditional on agreement. Conclave is intended to operationalize that mechanism first through confidential dataset procurement, and later through adjacent bilateral protocols.

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

For the currently implemented hackathon flow, Supabase OTP is the right call — the operator already knows who the participants are, and the implementation complexity of ZK alternatives isn't justified. For future bilateral procurement workflows, stronger identity/privacy choices may matter more depending on whether buyer/seller anonymity becomes part of the threat model.

---

## Project Structure

```
main.py                              # FastAPI app entry point
api/routes.py                        # REST endpoints — transport and state only, no skill logic
core/
├── models.py                        # Shared data models (Submission, OperatorConfig, SkillResponse, etc.)
├── skill_card.py                    # SkillCard — the internal contract every protocol declares
└── guardrails.py                    # LeakageDetector, OutputFilterBase (abstract)
skills/
├── router.py                        # SkillRouter — registers cards, dispatches invocations
├── hackathon_novelty/               # Fully implemented backend reference protocol
│   ├── __init__.py                  # skill_card + run_skill entry point
│   ├── models.py                    # HackathonSubmission, NoveltyResult
│   ├── deterministic.py             # Layer 1: embeddings, similarity, clustering
│   ├── agent.py                     # Layer 2: LangGraph multi-node graph
│   ├── tools.py                     # Triage and analysis tools exposed to the agent
│   ├── guardrails.py                # Layer 3: output filter
│   ├── init.py                      # Operator onboarding conversation handler
│   └── config.py                    # LLM and embedding model config for this protocol
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

## Adding a New Protocol

1. Create `skills/<name>/` with `models.py`, `deterministic.py`, `agent.py`, `guardrails.py`, `init.py`, `config.py`, `__init__.py`
2. Define a `<Name>Submission` extending `core.models.Submission`
3. Implement the three layers: deterministic → agent → guardrails
4. Implement an `init_handler` for operator onboarding (or omit for instant-start protocols)
5. Export a `skill_card` from `__init__.py`
6. Add one import line in `api/routes.py:register_skills()`

No changes needed to `core/`, `api/`, or the TEE infrastructure.

Note: the internal abstraction is still named `SkillCard` and the package directory is still `skills/`. That naming can change later without changing the product framing.

---

## Current Direction

The repo is moving in two parallel tracks:

1. **Runtime foundation** — shared TEE execution, auth, attestation, routing, role-based result ownership, and protocol packaging.
2. **Protocol workstreams** — concrete confidential workflows built on top of that runtime.

Current status:

- confidential data procurement is the flagship product direction
- the protocol is fully specified in `plans/confidential_data_procurement.md`
- procurement UI is expected to be built before the procurement backend is complete
- `hackathon_novelty` backend remains the main implemented reference protocol today
- the frontend is transitioning away from hackathon-only language toward procurement and NDAI-aligned workflows

Relevant planning docs:

- `plans/confidential_data_procurement.md`
- `plans/ui_changes.md`

---

## Known Limitations

- **State is in-memory only.** No persistence layer. Instance state is lost on restart.
- **Single-worker deployment assumed.** The submission threshold check is not atomic. Safe under uvicorn's default single-worker mode. Would need per-instance locking if changed to multi-worker.
- **`dataset_audit` is a stub.** The package structure exists but the pipeline is not implemented.
- **The NDAI-style procurement protocol is not implemented yet.** The main paper-aligned protocol is currently specified in planning docs, with UI work expected before backend completion.
- **Frontend is still transitional.** The `client/` Next.js app still contains hackathon-centric flows while procurement UI is being designed and prototyped.
- **`/register` (dev fallback) is open to anyone** who knows the `instance_id`. In production, use `/auth/send-otp` + `/auth/verify-otp` with Supabase configured.
- **CORS is permissive (`*`).** Appropriate for enclave deployment where the client origin isn't fixed, but worth reviewing per deployment.
