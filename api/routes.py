from __future__ import annotations
import asyncio
import secrets
import uuid
from functools import partial

from fastapi import APIRouter, HTTPException, Request

from core.models import SkillResponse, InitRequest, InitResponse
from skills.router import SkillRouter

router = APIRouter()

# Instance-scoped in-memory stores
_instances: dict[str, dict] = {}
# instance_id -> {skill_name, config, threshold, conversation[], triggered}

_submissions: dict[str, dict] = {}
# instance_id -> {submission_id -> raw_dict}

_results: dict[str, dict] = {}
# instance_id -> {submission_id -> result_dict}

_tokens: dict[str, dict] = {}
# token_string -> {instance_id, role}

_skill_router = SkillRouter()


def register_skills():
    """Register all skills. Called at startup."""
    from skills.hackathon_novelty import skill_card
    _skill_router.register(skill_card)


# --- Helpers ---

def _resolve_token(request: Request) -> dict:
    """Read X-Instance-Token header and resolve to {instance_id, role}."""
    token = request.headers.get("X-Instance-Token")
    if not token:
        raise HTTPException(status_code=401, detail="X-Instance-Token header required")
    if token not in _tokens:
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    return _tokens[token]


async def _run_pipeline(instance_id: str) -> int:
    """Validate submissions, invoke skill pipeline, store results. Returns result count."""
    inst = _instances[instance_id]
    card = _skill_router.get_card(inst["skill_name"])
    subs = _submissions.get(instance_id, {})

    try:
        inputs = [card.input_model(**s) for s in subs.values()]
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Submission validation failed: {e}")

    loop = asyncio.get_event_loop()
    response: SkillResponse = await loop.run_in_executor(
        None,
        partial(_skill_router.invoke, inst["skill_name"], inputs=inputs, params=inst["config"]),
    )

    _results.setdefault(instance_id, {})
    for r in response.results:
        _results[instance_id][r["submission_id"]] = r

    inst["triggered"] = True
    return len(response.results)


# --- Endpoints ---

@router.post("/init")
async def init_instance(body: InitRequest):
    """
    Conversational operator onboarding loop.

    First call: instance_id=None — creates instance, starts conversation.
    Subsequent calls: include instance_id to continue the conversation.
    The skill's init_handler owns all onboarding logic (prompts, LLM calls, config extraction).
    Returns status='configuring' (skill needs more info) or status='ready' (tokens issued).
    """
    if body.instance_id is None:
        card = _skill_router.get_card(body.skill_name)
        if card.init_handler is None:
            raise HTTPException(status_code=400, detail=f"Skill '{body.skill_name}' does not support conversational setup")
        instance_id = str(uuid.uuid4())
        _instances[instance_id] = {
            "skill_name": body.skill_name,
            "config": None,
            "threshold": card.config.get("min_submissions", 5),
            "conversation": [],
            "triggered": False,
        }
        _submissions[instance_id] = {}
        _results[instance_id] = {}
    else:
        instance_id = body.instance_id
        if instance_id not in _instances:
            raise HTTPException(status_code=404, detail="Instance not found")
        card = _skill_router.get_card(_instances[instance_id]["skill_name"])

    inst = _instances[instance_id]

    # Delegate entirely to the skill's init_handler — sync call wrapped in executor
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, card.init_handler, body.message, inst["conversation"]
    )

    # Store updated conversation returned by the handler
    inst["conversation"] = result["conversation"]

    if result["status"] == "ready":
        inst["config"] = result["config"]
        inst["config"].instance_id = instance_id
        inst["threshold"] = result.get("threshold", inst["threshold"])

        operator_token = secrets.token_urlsafe(16)
        participant_token = secrets.token_urlsafe(16)
        _tokens[operator_token] = {"instance_id": instance_id, "role": "operator"}
        _tokens[participant_token] = {"instance_id": instance_id, "role": "participant"}

        return InitResponse(
            instance_id=instance_id,
            status="ready",
            message=result["message"],
            operator_token=operator_token,
            participant_token=participant_token,
        )

    return InitResponse(
        instance_id=instance_id,
        status="configuring",
        message=result["message"],
    )


@router.get("/health")
def health():
    total_subs = sum(len(s) for s in _submissions.values())
    return {
        "status": "ok",
        "instances": len(_instances),
        "submissions": total_subs,
        "skills": _skill_router.list_skills(),
    }


@router.post("/submit")
async def submit(submission: dict, request: Request):
    """
    Accept a submission for an instance.
    Auto-triggers the pipeline when submission count reaches the threshold.
    Re-triggers on every subsequent submission so all scores stay current.
    """
    token_info = _resolve_token(request)
    instance_id = token_info["instance_id"]

    sid = submission.get("submission_id")
    if not sid:
        raise HTTPException(status_code=422, detail="submission_id is required")

    _submissions[instance_id][sid] = submission
    count = len(_submissions[instance_id])
    threshold = _instances[instance_id]["threshold"]

    if count >= threshold:
        await _run_pipeline(instance_id)
        return {
            "submission_id": sid,
            "status": "received_analysis_complete",
            "submissions_count": count,
        }

    return {
        "submission_id": sid,
        "status": "received_pending",
        "submissions_count": count,
        "threshold": threshold,
    }


@router.post("/trigger")
async def trigger(request: Request):
    """Manual pipeline trigger. Operator only. Uses stored instance config."""
    token_info = _resolve_token(request)
    if token_info["role"] != "operator":
        raise HTTPException(status_code=403, detail="Only operator can trigger manually")

    instance_id = token_info["instance_id"]
    if not _submissions.get(instance_id):
        raise HTTPException(status_code=400, detail="No submissions to analyze")

    count = await _run_pipeline(instance_id)
    return {"status": "complete", "results_count": count}


@router.get("/results")
def get_all_results(request: Request):
    """Return all results for the instance. Operator only."""
    token_info = _resolve_token(request)
    if token_info["role"] != "operator":
        raise HTTPException(status_code=403, detail="Only operator can view all results")

    instance_id = token_info["instance_id"]
    return {"results": list(_results.get(instance_id, {}).values())}


@router.get("/results/{submission_id}")
def get_results(submission_id: str, request: Request):
    """
    Return result for a single submission.
    Participant: only sees their own result (submission_id must match).
    Operator: can see any submission's result.
    """
    token_info = _resolve_token(request)
    instance_id = token_info["instance_id"]
    role = token_info["role"]

    instance_results = _results.get(instance_id, {})

    if submission_id not in instance_results:
        raise HTTPException(status_code=404, detail="Result not found or not yet available")

    if role == "participant":
        # Participants can only retrieve their own result
        # The submission_id path param is the identifier — no further check needed
        # since participants know their own submission_id
        return instance_results[submission_id]

    return instance_results[submission_id]


@router.get("/skills")
def list_skills():
    """Return rich metadata for all registered skills."""
    return {"skills": _skill_router.list_cards()}


@router.get("/skills/{skill_name}")
def get_skill(skill_name: str):
    """Return metadata for a single skill."""
    try:
        return _skill_router.get_card(skill_name).metadata()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
