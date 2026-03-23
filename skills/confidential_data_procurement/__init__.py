"""
Entry point for the confidential_data_procurement skill.

Pipeline (per submission — threshold=1, so always exactly one):
    0. ingest.py          — CSV parse + metadata parse (no LLM)
    1. deterministic.py   — quality metrics, component scores, price, deal check (no LLM)
    2. agent.py           — schema matching, claim verification, explanation (LLM)
    3. guardrails.py      — role-aware key filter, score clamping, leakage detection
    4. respond_handler    — deal response + one-round renegotiation (3×3 resolution matrix)

What to edit here:
- run_skill(): change how deterministic + agent results merge
- respond_handler / _resolve(): update renegotiation logic
- skill_card: update description, config, trigger_modes, roles, user_display

The skill_card is consumed by the SkillRouter and the /skills API endpoint.
"""
from __future__ import annotations

import secrets as _secrets

from core.models import SkillResponse
from core.skill_card import SkillCard
from skills.confidential_data_procurement.agent import run_agent
from skills.confidential_data_procurement.config import (
    ALLOWED_OUTPUT_KEYS,
    USER_OUTPUT_KEYS,
)
from skills.confidential_data_procurement.deterministic import (
    check_deal,
    compute_price,
    compute_quality_score,
    run_deterministic,
)
from skills.confidential_data_procurement.guardrails import ProcurementFilter
from skills.confidential_data_procurement.init import procurement_init_handler
from skills.confidential_data_procurement.ingest import get_dataset, procurement_upload_handler
from skills.confidential_data_procurement.models import (
    BuyerPolicy,
    ProcurementResult,
    SupplierSubmission,
)
from skills.confidential_data_procurement.tools import set_context


def run_skill(inputs: list[SupplierSubmission], params: BuyerPolicy) -> SkillResponse:
    """
    Full pipeline: deterministic → [agent — Commit 7] → guardrails → response.

    With threshold=1, inputs always has exactly one SupplierSubmission.
    The dataset DataFrame lives in the ingest store — never serialized or passed to LLM.
    """
    results = []

    for sub in inputs:
        det = run_deterministic(sub.dataset_id, params, sub.reserve_price)
        metrics = det["metrics"]

        if metrics.critical_failure:
            result = ProcurementResult(
                submission_id=sub.submission_id,
                deal=False,
                quality_score=0.0,
                component_scores={},
                proposed_payment=params.base_price,
                hard_constraints_pass=False,
                settlement_status="rejected",
                notes=det["notes"],
            )
        else:
            # Agent layer — schema matching + claim verification + explanation
            dataset = get_dataset(sub.dataset_id)
            set_context(sub.dataset_id, {
                "required_columns": params.required_columns,
                "column_definitions": dataset.get("column_definitions") or {},
                "seller_claims": dataset.get("seller_claims") or {},
            })
            agent_result = run_agent(sub.dataset_id, params, metrics, det["component_scores"])

            # Merge agent's refined scores into component_scores, recompute quality
            component_scores = {**det["component_scores"]}
            component_scores["schema"] = agent_result["schema_score"]
            component_scores["claim_veracity"] = agent_result["claim_veracity_score"]

            quality_score = compute_quality_score(component_scores, params)
            proposed_payment = compute_price(quality_score, params.base_price, params.max_budget)
            deal = check_deal(
                metrics.hard_constraints_pass, sub.reserve_price,
                proposed_payment, params.max_budget,
            )
            settlement_status = "pending_approval" if deal else "rejected"

            result = ProcurementResult(
                submission_id=sub.submission_id,
                deal=deal,
                quality_score=quality_score,
                component_scores=component_scores,
                proposed_payment=proposed_payment,
                hard_constraints_pass=metrics.hard_constraints_pass,
                settlement_status=settlement_status,
                notes=det["notes"],
                explanation=agent_result.get("explanation"),
                schema_matching=agent_result.get("schema_matching"),
                claim_verification=agent_result.get("claim_verification"),
            )

        result_dict = result.model_dump()
        result_dict["_dataset_id"] = sub.dataset_id  # internal — for post-deal download
        results.append(result_dict)

    # Guardrails — admin-level filter stores all allowed keys.
    # Role-based filtering (buyer vs supplier) happens in routes.py GET /results.
    output_filter = ProcurementFilter(role="admin")
    filtered = output_filter.apply(results, raw_inputs=[])

    return SkillResponse(skill="confidential_data_procurement", results=filtered)


def procurement_respond_handler(
    result: dict,
    action: str,
    revised_value: float | None,
    role: str,          # "buyer" or "supplier" (mapped from "admin"/"user" in routes.py)
    policy: BuyerPolicy,
) -> dict:
    """
    Process one deal response and advance the settlement state machine.

    3×3 resolution matrix (B = buyer, S = supplier):

        B \\ S  | accept | reject | renegotiate
        --------|--------|--------|------------
        accept  | auth   | reject | auth*
        reject  | reject | reject | reject
        reneg   | auth*  | reject | check†

    * auth at proposed_payment — the acceptor already committed
    † auth if revised_budget >= revised_reserve, else rejected

    One renegotiation round only — ValueError if renegotiation_used is True.
    revised_value is required when action='renegotiate'.
    """
    result = dict(result)   # shallow copy — don't mutate caller's dict

    if action == "renegotiate":
        if result.get("renegotiation_used"):
            raise ValueError("Renegotiation already used. Only one round is allowed.")
        if revised_value is None:
            raise ValueError("revised_value is required when action='renegotiate'.")
        if role == "buyer":
            revised_value = float(revised_value)
            if revised_value < (policy.base_price or 0.0):
                raise ValueError(
                    f"Revised payment (${revised_value:,.2f}) cannot be below "
                    f"base price (${policy.base_price:,.2f})."
                )
            if revised_value > policy.max_budget:
                raise ValueError(
                    f"Revised payment (${revised_value:,.2f}) cannot exceed "
                    f"max budget (${policy.max_budget:,.2f})."
                )
        else:  # supplier
            revised_value = float(revised_value)
            if revised_value < 0:
                raise ValueError("Revised reserve price cannot be negative.")

    # Store this party's response
    if role == "buyer":
        result["buyer_response"] = action
        if action == "renegotiate":
            result["revised_budget"] = revised_value
    else:
        result["supplier_response"] = action
        if action == "renegotiate":
            result["revised_reserve"] = revised_value

    # If both parties have now responded, resolve; otherwise await counterparty
    buyer_resp = result.get("buyer_response")
    supplier_resp = result.get("supplier_response")

    if buyer_resp is None or supplier_resp is None:
        result["settlement_status"] = "awaiting_counterparty"
        return result

    return _resolve(result)


def _resolve(result: dict) -> dict:
    """Apply the 3×3 matrix once both buyer_response and supplier_response are set."""
    buyer_resp = result["buyer_response"]
    supplier_resp = result["supplier_response"]

    # Any reject → deal off
    if buyer_resp == "reject" or supplier_resp == "reject":
        result["settlement_status"] = "rejected"
        result["deal"] = False
        return result

    # Both accept → authorized
    if buyer_resp == "accept" and supplier_resp == "accept":
        result["settlement_status"] = "authorized"
        result["deal"] = True
        result["release_token"] = _secrets.token_urlsafe(16)
        return result

    # One accepts + other renegotiates → honor the acceptor's bound (proposed_payment)
    if buyer_resp == "accept" or supplier_resp == "accept":
        result["settlement_status"] = "authorized"
        result["deal"] = True
        result["renegotiation_used"] = True
        result["release_token"] = _secrets.token_urlsafe(16)
        return result

    # Both renegotiate → check if revised terms meet
    result["renegotiation_used"] = True
    revised_budget = float(result.get("revised_budget") or result.get("proposed_payment") or 0)
    revised_reserve = float(result.get("revised_reserve") or 0)

    if revised_budget >= revised_reserve:
        result["settlement_status"] = "authorized"
        result["deal"] = True
        result["proposed_payment"] = revised_budget
        result["release_token"] = _secrets.token_urlsafe(16)
    else:
        result["settlement_status"] = "rejected"
        result["deal"] = False
        note = (
            f"Renegotiation failed: buyer's revised offer (${revised_budget:,.2f}) "
            f"is below supplier's revised reserve (${revised_reserve:,.2f})."
        )
        notes = list(result.get("notes") or [])
        notes.append(note)
        result["notes"] = notes

    return result


skill_card = SkillCard(
    name="confidential_data_procurement",
    description=(
        "Bilateral confidential dataset trade protocol. A buyer defines acquisition "
        "policy and budget; a supplier uploads a CSV dataset with a reserve price. "
        "The TEE evaluates data quality (null rates, duplicates, schema match, claim "
        "verification) and proposes a fair price — neither party sees the other's "
        "private numbers. Only derived quality metrics and the deal verdict leave "
        "the enclave."
    ),
    run=run_skill,
    input_model=SupplierSubmission,
    output_keys=ALLOWED_OUTPUT_KEYS,
    user_output_keys=USER_OUTPUT_KEYS,
    config={"min_submissions": 1},
    trigger_modes=[
        {
            "mode": "instant",
            "description": (
                "Pipeline fires immediately when the supplier submits. "
                "Each submission is evaluated independently against the buyer's policy."
            ),
            "default_config": {"min_submissions": 1},
            "admin_configurable": False,
        },
    ],
    roles={
        "admin": {
            "description": (
                "Data buyer. Initialises the instance with an acquisition policy "
                "(required columns, quality thresholds, budget range). Sees full "
                "quality scores and proposed payment. Can accept, reject, or "
                "renegotiate the deal."
            ),
            "capabilities": ["configure", "view_all_results", "respond"],
        },
        "user": {
            "description": (
                "Data supplier. Uploads a CSV dataset and metadata, sets a reserve "
                "price, and submits for evaluation. Sees the proposed payment and "
                "deal verdict but NOT the quality score (to prevent budget "
                "reverse-engineering). Can accept, reject, or renegotiate."
            ),
            "capabilities": ["upload", "submit", "respond"],
            "result_view": "own",
        },
    },
    setup_prompt=(
        "This skill runs a confidential dataset trade inside a TEE. "
        "No raw data or private budget numbers ever leave the enclave.\n\n"
        "As the buyer (admin), you need to provide:\n"
        "1. **Required columns** — the column names you expect in the dataset.\n"
        "2. **Quality thresholds** — minimum rows, max null rate, max duplicate rate.\n"
        "3. **Budget** — your maximum budget and optional base (floor) price.\n"
        "4. **(Optional)** Label column + minimum label rate.\n"
        "5. **(Optional)** Forbidden columns — PII fields to automatically block.\n\n"
        "The supplier will upload a CSV + metadata and set a reserve price. "
        "The TEE computes a quality score, proposes a fair price, and checks "
        "if the deal is viable (reserve ≤ price ≤ budget). Both parties then "
        "accept, reject, or renegotiate."
    ),
    init_handler=procurement_init_handler,
    upload_handler=procurement_upload_handler,
    respond_handler=procurement_respond_handler,
    user_display={
        "deal":               {"type": "badge",  "label": "Deal Status"},
        "quality_score":      {"type": "gauge",  "label": "Quality Score", "min": 0, "max": 1},
        "proposed_payment":   {"type": "currency", "label": "Proposed Payment"},
        "settlement_status":  {"type": "badge",  "label": "Settlement"},
        "notes":              {"type": "list",   "label": "Notes"},
        "explanation":        {"type": "text",   "label": "Analysis"},
        "schema_matching":    {"type": "json",   "label": "Schema Matching"},
        "claim_verification": {"type": "json",   "label": "Claim Verification"},
    },
)
