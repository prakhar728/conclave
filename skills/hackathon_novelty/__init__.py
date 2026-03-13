"""
Entry point for the hackathon_novelty skill.

3-layer pipeline:
    1. deterministic.py  — embeddings, similarity, novelty scores, clustering (no LLM)
    2. agent.py          — multi-node LangGraph graph (triage → router → flag/quick/analyze → finalize)
    3. guardrails.py     — key whitelist, score clamping, leakage detection

What to edit here:
- run_skill(): change how triage_context is built (what signals the triage node receives)
- ALLOWED_OUTPUT_KEYS: add new output fields in config.py — this file doesn't need to change
- skill_card: update description or config if skill metadata changes

The skill_card is consumed by the SkillRouter and the /skills API endpoint.
Adding a field to NoveltyResult + ALLOWED_OUTPUT_KEYS is all that's needed to expose it in /results.
"""
from __future__ import annotations
from core.models import OperatorConfig, SkillResponse
from core.skill_card import SkillCard
from skills.hackathon_novelty.models import HackathonSubmission, NoveltyResult
from skills.hackathon_novelty.deterministic import run_deterministic
from skills.hackathon_novelty.tools import set_context
from skills.hackathon_novelty.agent import run_agent
from skills.hackathon_novelty.guardrails import HackathonNoveltyFilter
from skills.hackathon_novelty.config import ALLOWED_OUTPUT_KEYS, MIN_SUBMISSIONS


def run_skill(inputs: list[HackathonSubmission], params: OperatorConfig) -> SkillResponse:
    """Full 3-layer pipeline: deterministic → agent (multi-node graph) → guardrails → response."""

    if len(inputs) < MIN_SUBMISSIONS:
        return SkillResponse(
            skill="hackathon_novelty",
            results=[{"submission_id": s.submission_id, "status": "insufficient_submissions"} for s in inputs],
        )

    # Layer 1: Deterministic
    det = run_deterministic(inputs)

    # Build submissions map and set tool context
    submissions_map = {s.submission_id: s for s in inputs}
    set_context(det, submissions_map)

    # Build triage_context — rich signals the triage LLM uses to classify each submission
    # Add more signals here as new tools or deterministic outputs become available
    clusters = det["clusters"]
    triage_context = {}
    for i, sid in enumerate(det["submission_ids"]):
        sub = submissions_map[sid]
        triage_context[sid] = {
            "novelty_score": float(det["novelty_scores"][i]),
            "percentile": float(det["percentiles"][i]),
            "cluster": clusters[i],
            "cluster_size": clusters.count(clusters[i]),
            "has_repo": sub.repo_summary is not None,
            "has_deck": sub.deck_text is not None,
        }

    # Layer 2: Agent (multi-node graph)
    agent_results = run_agent(
        submission_ids=det["submission_ids"],
        criteria=params.criteria,
        guidelines=params.guidelines,
        triage_context=triage_context,
    )

    # Merge deterministic + agent results into NoveltyResult objects
    agent_map = {r["submission_id"]: r for r in agent_results}
    results = []
    for i, sid in enumerate(det["submission_ids"]):
        ar = agent_map.get(sid, {})
        result = NoveltyResult(
            submission_id=sid,
            novelty_score=float(det["novelty_scores"][i]),
            percentile=float(det["percentiles"][i]),
            cluster=det["clusters"][i],
            criteria_scores=ar.get("criteria_scores", {}),
            status=ar.get("status", "analyzed"),
            analysis_depth=ar.get("analysis_depth", "full"),
            duplicate_of=ar.get("duplicate_of", None),
        )
        results.append(result.model_dump())

    # Layer 3: Guardrails
    output_filter = HackathonNoveltyFilter()
    raw_inputs = [s.idea_text + (s.repo_summary or "") + (s.deck_text or "") for s in inputs]
    filtered_results = output_filter.apply(results, raw_inputs)

    return SkillResponse(skill="hackathon_novelty", results=filtered_results)


skill_card = SkillCard(
    name="hackathon_novelty",
    description=(
        "Scores hackathon submissions for novelty using embedding similarity, "
        "KMeans clustering, and a multi-node LangGraph agent (triage → analysis → guardrails). "
        "Raw submission content is accessible to the LLM inside the TEE; "
        "only derived outputs leave the pipeline."
    ),
    run=run_skill,
    input_model=HackathonSubmission,
    output_keys=ALLOWED_OUTPUT_KEYS,
    config={"min_submissions": MIN_SUBMISSIONS},
)
