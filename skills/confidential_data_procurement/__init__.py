"""
Entry point for the confidential_data_procurement skill.

Pipeline (per submission — threshold=1, so always exactly one):
    0. ingest.py          — CSV parse + metadata parse (no LLM)
    1. deterministic.py   — quality metrics, component scores, price, deal check (no LLM)
    2. agent.py           — schema matching, claim verification, explanation (LLM) [Commit 7]
    3. guardrails.py      — role-aware key filter, score clamping, leakage detection

What to edit here:
- run_skill(): change how deterministic + agent results merge
- skill_card: update description, config, trigger_modes, roles, user_display

The skill_card is consumed by the SkillRouter and the /skills API endpoint.
respond_handler will be added in Commit 8 (renegotiation).
"""
from __future__ import annotations

from core.models import SkillResponse
from core.skill_card import SkillCard
from skills.confidential_data_procurement.config import (
    ALLOWED_OUTPUT_KEYS,
    USER_OUTPUT_KEYS,
)
from skills.confidential_data_procurement.deterministic import run_deterministic
from skills.confidential_data_procurement.guardrails import ProcurementFilter
from skills.confidential_data_procurement.init import procurement_init_handler
from skills.confidential_data_procurement.ingest import cleanup, procurement_upload_handler
from skills.confidential_data_procurement.models import (
    BuyerPolicy,
    ProcurementResult,
    SupplierSubmission,
)


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
                proposed_payment=params.base_price,
                hard_constraints_pass=False,
                settlement_status="rejected",
                notes=det["notes"],
            )
        else:
            # --- Agent layer (Commit 7) will refine these placeholders ---
            # schema_score stays 0.5, claim_veracity stays 1.0
            # Agent will populate: explanation, claim_verification, schema_matching
            # and update quality_score / proposed_payment accordingly

            settlement_status = "pending_approval" if det["deal"] else "rejected"

            result = ProcurementResult(
                submission_id=sub.submission_id,
                deal=det["deal"],
                quality_score=det["quality_score"],
                proposed_payment=det["proposed_payment"],
                hard_constraints_pass=metrics.hard_constraints_pass,
                settlement_status=settlement_status,
                notes=det["notes"],
            )

        results.append(result.model_dump())

    # Guardrails — admin-level filter stores all allowed keys.
    # Role-based filtering (buyer vs supplier) happens in routes.py GET /results.
    output_filter = ProcurementFilter(role="admin")
    filtered = output_filter.apply(results, raw_inputs=[])

    return SkillResponse(skill="confidential_data_procurement", results=filtered)


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
    respond_handler=None,   # Commit 8
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
