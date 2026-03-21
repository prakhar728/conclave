# Conclave — NDAI Skills Service

Multi-party TEE platform where sensitive data goes in and only derived outputs come out. Built for scenarios where multiple parties need AI-generated insights from each other's data without anyone — including the platform operators — seeing the raw inputs.

Each use case is a **skill**: a self-contained analysis pipeline running inside a Trusted Execution Environment. The platform is a template gallery — anyone can build a skill for their domain, and the TEE guarantees that raw data never leaves the enclave.

---

## How It Works

1. **Admin** creates an instance by configuring a skill via `/init` (multi-turn LLM conversation)
2. **Users** submit data via `/submit` — each submission is stored inside the TEE
3. Pipeline auto-triggers once enough submissions arrive (or admin triggers manually)
4. Each user sees only their own result. Admin sees aggregated results. No one sees raw inputs.

Two access levels:
- **Admin** — configures the instance, triggers evaluation, views all results
- **User** — submits data, views only their own result

Tokens (`admin_token` and `user_token`) are issued when the instance is created and sent as `X-Instance-Token` headers on all subsequent requests.

---

## Quickstart

```bash
cp .env.example .env          # add your LLM API key
pip install -r requirements.txt
uvicorn main:app --reload     # http://localhost:8000
```

Or with Docker:

```bash
docker-compose up
```

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/init` | None | Instance setup loop — call until `status="ready"`, receive `admin_token` + `user_token` |
| `POST` | `/submit` | Any | Submit data; auto-triggers pipeline at threshold |
| `POST` | `/trigger` | Admin | Manual pipeline trigger |
| `GET` | `/results` | Admin | All results for instance |
| `GET` | `/results/{id}` | Any | Single result (users see own, admin sees any) |
| `GET` | `/skills` | None | Metadata for all registered skills |
| `GET` | `/skills/{name}` | None | Metadata for one skill |
| `GET` | `/health` | None | Status check |

---

## Skills

Each skill follows a 3-layer pipeline pattern:

1. **Deterministic** — pure computation, no LLM (embeddings, statistics, clustering)
2. **Agent** — LangGraph-based evaluation with constrained tool access
3. **Guardrails** — programmatic output filter (key whitelist, score clamping, leakage detection)

Every skill declares its contract via a `SkillCard`: input schema, allowed output keys, trigger modes, role definitions, and an onboarding handler. The API consumes these declarations without knowing skill internals.

### Built-in Skills

| Skill | Input | Output | Status |
|-------|-------|--------|--------|
| `hackathon_novelty` | Idea text, repo summary, pitch deck | Novelty score, criteria scores, percentile, cluster | Fully implemented |
| `dataset_audit` | Raw dataset | Quality report (shape, nulls, distributions) | Stub |

---

## Project Structure

```
api/routes.py                        # REST endpoints — pure plumbing, no skill logic
core/
├── models.py                        # Submission, OperatorConfig, SkillResponse, InitRequest/Response
├── skill_card.py                    # SkillCard dataclass — the contract every skill declares
├── guardrails.py                    # LeakageDetector, OutputFilterBase (abstract)
skills/
├── router.py                        # SkillRouter — registers cards, dispatches invocations
├── hackathon_novelty/
│   ├── deterministic.py             # Layer 1: embeddings, similarity, clustering
│   ├── agent.py                     # Layer 2: multi-node LangGraph graph
│   ├── guardrails.py                # Layer 3: output filter
│   ├── init.py                      # Admin onboarding (LLM conversation loop)
│   ├── models.py                    # HackathonSubmission, NoveltyResult
│   └── __init__.py                  # skill_card + run_skill entry point
├── dataset_audit/                   # Stub — same pattern
tests/                               # 47 tests, all mocked (no API keys needed)
config.py                            # LLM provider selection (OpenAI/Anthropic/Google)
```

---

## Adding a New Skill

1. Create `skills/<name>/` with `models.py`, `deterministic.py`, `guardrails.py`, `config.py`, `init.py`, `__init__.py`
2. Define a `<Name>Submission` extending `core.models.Submission` with your input fields
3. Implement the 3 layers (deterministic → agent → guardrails)
4. Implement an `init_handler` for admin onboarding (or omit for instant skills)
5. Export a `skill_card` from `__init__.py` declaring all metadata
6. Add one import line in `api/routes.py:register_skills()`

No changes needed to `core/`, `api/`, or the TEE infrastructure.

---

## Running Tests

```bash
python -m pytest tests/ -v    # 54 tests, no API keys needed
```

CI runs automatically on every push via GitHub Actions.
