# Conclave — NDAI Skills Service

Multi-party TEE platform: sensitive data goes in, only derived outputs come out. Each **skill** is a self-contained pipeline (deterministic → LangGraph agent → guardrails) running inside an enclave. Raw submissions never leave.

---

## Quickstart

```bash
cp .env.example .env          # add your API key
pip install -r requirements.txt
uvicorn main:app --reload     # http://localhost:8000
```

Or with Docker:

```bash
docker-compose up
```

---

## API Endpoints

All submission/result endpoints require `X-Instance-Token` header (issued by `/init`).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/init` | None | Operator onboarding loop — call until `status="ready"`, receive tokens |
| `POST` | `/submit` | Token | Submit entry; auto-triggers pipeline at threshold |
| `POST` | `/trigger` | Operator | Manual pipeline trigger |
| `GET` | `/results` | Operator | All results for instance |
| `GET` | `/results/{id}` | Token | Single result (participant sees own, operator sees any) |
| `GET` | `/skills` | None | Metadata for all registered skills |
| `GET` | `/skills/{name}` | None | Metadata for one skill |
| `GET` | `/health` | None | Status check |

---

## Running Tests

```bash
python -m pytest tests/ -v    # 47 tests, no API keys needed
```

CI runs the same suite on every push via GitHub Actions (`.github/workflows/ci.yml`).

---

## Project Structure

```
skills/hackathon_novelty/    # Skill 1: fully implemented
├── deterministic.py         # Layer 1: embeddings, similarity, clustering
├── agent.py                 # Layer 2: multi-node LangGraph graph
├── guardrails.py            # Layer 3: key whitelist, score clamping, leakage detection
├── init.py                  # Operator onboarding (LLM conversation loop)
└── __init__.py              # skill_card + run_skill entry point

core/                        # Shared infrastructure (no skill logic)
api/routes.py                # REST endpoints — pure plumbing
```

---

## Adding a New Skill

Create `skills/<name>/` with the 3-layer pipeline and a `SkillCard`. Register it in `api/routes.py:register_skills()`. Zero changes to core or API. See `plan.md` for full details.
