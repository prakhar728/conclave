"""
Deterministic quality evaluation layer for confidential_data_procurement.

No LLM calls. Pure pandas + math.

Pipeline:
  1. compute_metrics()       — null rates, duplicate rate, label rate, forbidden col check
  2. check_critical()        — early exit if any hard constraint is fatally violated
  3. compute_component_scores() — each dimension scored [0, 1]
  4. compute_quality_score() — weighted sum clamped to [0, 1]
  5. compute_price()         — P = base_price + (max_budget - base_price) * S
  6. check_deal()            — R <= P <= B and hard_constraints_pass
  7. run_deterministic()     — orchestrates all of the above

Note: schema_score and claim_veracity are placeholders (0.5 and 1.0 respectively)
until the agent layer runs fuzzy column matching and claim verification.
run_skill() will merge the agent's verdicts into the final quality score.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from skills.confidential_data_procurement.config import (
    CRITICAL_DUPLICATE_THRESHOLD,
    DEFAULT_SCORE_WEIGHTS,
)
from skills.confidential_data_procurement.ingest import get_dataset
from skills.confidential_data_procurement.models import BuyerPolicy, DatasetMetrics


# ---------------------------------------------------------------------------
# Step 1: Metrics
# ---------------------------------------------------------------------------

def compute_metrics(df: pd.DataFrame, policy: BuyerPolicy) -> DatasetMetrics:
    """Compute all quality metrics from the raw DataFrame."""
    row_count = len(df)
    column_names = list(df.columns)

    # Null rates per column and overall
    null_rate_by_column = {col: float(df[col].isna().mean()) for col in df.columns}
    total_cells = df.size
    overall_null_rate = float(df.isna().sum().sum() / total_cells) if total_cells > 0 else 0.0

    # Duplicate rate
    duplicate_rate = float(df.duplicated().mean()) if row_count > 0 else 0.0

    # Label rate — fraction of positive/truthy values in label column
    label_rate: float | None = None
    if policy.label_column and policy.label_column in df.columns:
        col = df[policy.label_column].dropna()
        if len(col) > 0:
            label_rate = float((col.astype(bool)).mean())

    # Forbidden columns present
    forbidden_columns_present = [
        col for col in policy.forbidden_columns if col in column_names
    ]

    # Hard constraints: forbidden cols absent + not critical duplicate rate
    hard_constraints_pass = (
        len(forbidden_columns_present) == 0
        and duplicate_rate < CRITICAL_DUPLICATE_THRESHOLD
        and row_count > 0
    )

    # Critical failure detection
    critical_failure = False
    critical_reason: str | None = None

    if row_count == 0:
        critical_failure = True
        critical_reason = "Dataset is empty — no rows to evaluate."
    elif forbidden_columns_present:
        critical_failure = True
        critical_reason = (
            f"Forbidden column(s) detected: {', '.join(forbidden_columns_present)}. "
            "Deal rejected to protect data privacy constraints."
        )
    elif duplicate_rate >= CRITICAL_DUPLICATE_THRESHOLD:
        critical_failure = True
        critical_reason = (
            f"Duplicate rate ({duplicate_rate:.1%}) exceeds critical threshold "
            f"({CRITICAL_DUPLICATE_THRESHOLD:.0%}). Dataset quality is insufficient."
        )

    return DatasetMetrics(
        row_count=row_count,
        column_names=column_names,
        null_rate_by_column=null_rate_by_column,
        overall_null_rate=overall_null_rate,
        duplicate_rate=duplicate_rate,
        label_rate=label_rate,
        forbidden_columns_present=forbidden_columns_present,
        hard_constraints_pass=hard_constraints_pass,
        critical_failure=critical_failure,
        critical_reason=critical_reason,
    )


# ---------------------------------------------------------------------------
# Step 2: Critical check
# ---------------------------------------------------------------------------

def check_critical(metrics: DatasetMetrics) -> tuple[bool, str | None]:
    """Return (is_critical, reason). Caller should early-exit if is_critical."""
    return metrics.critical_failure, metrics.critical_reason


# ---------------------------------------------------------------------------
# Step 3: Component scores
# ---------------------------------------------------------------------------

def compute_component_scores(
    metrics: DatasetMetrics, policy: BuyerPolicy
) -> dict[str, float]:
    """
    Score each quality dimension in [0, 1].

    schema_score:     0.5 placeholder — agent will compute fuzzy match verdict.
    claim_veracity:   1.0 placeholder — agent will compute claim verification score.
    """
    scores: dict[str, float] = {}

    # Schema — agent will refine this
    scores["schema"] = 0.5

    # Coverage: how close are we to the required row count?
    scores["coverage"] = min(metrics.row_count / policy.min_rows, 1.0)

    # Null score: penalise for null rate exceeding the policy threshold
    if policy.max_null_rate > 0:
        scores["null"] = max(0.0, 1.0 - (metrics.overall_null_rate / policy.max_null_rate))
    else:
        scores["null"] = 1.0 if metrics.overall_null_rate == 0 else 0.0

    # Duplicate score
    if policy.max_duplicate_rate > 0:
        scores["duplicate"] = max(
            0.0, 1.0 - (metrics.duplicate_rate / policy.max_duplicate_rate)
        )
    else:
        scores["duplicate"] = 1.0 if metrics.duplicate_rate == 0 else 0.0

    # Label score
    if policy.min_label_rate is not None and policy.min_label_rate > 0:
        label_rate = metrics.label_rate or 0.0
        scores["label"] = min(label_rate / policy.min_label_rate, 1.0)
    else:
        scores["label"] = 1.0  # not required

    # Risk score: hard 0 if forbidden columns present
    scores["risk"] = 0.0 if metrics.forbidden_columns_present else 1.0

    # Claim veracity — agent will refine this
    scores["claim_veracity"] = 1.0

    return scores


# ---------------------------------------------------------------------------
# Step 4: Weighted quality score
# ---------------------------------------------------------------------------

def compute_quality_score(
    component_scores: dict[str, float], policy: BuyerPolicy
) -> float:
    """
    Weighted sum of component scores, clamped to [0, 1].
    Uses policy.score_weights if set, otherwise DEFAULT_SCORE_WEIGHTS.
    """
    weights = policy.score_weights if policy.score_weights else DEFAULT_SCORE_WEIGHTS
    total = sum(
        weights.get(key, 0.0) * score for key, score in component_scores.items()
    )
    return max(0.0, min(1.0, total))


# ---------------------------------------------------------------------------
# Step 5: Price
# ---------------------------------------------------------------------------

def compute_price(S: float, base_price: float, max_budget: float) -> float:
    """
    P = base_price + (max_budget - base_price) * S

    S=0 → P = base_price  (floor: minimum payment even for poor quality)
    S=1 → P = max_budget  (ceiling: full payment for perfect quality)
    """
    return round(base_price + (max_budget - base_price) * S, 2)


# ---------------------------------------------------------------------------
# Step 6: Deal condition
# ---------------------------------------------------------------------------

def check_deal(
    hard_constraints_pass: bool,
    reserve_price: float,
    proposed_payment: float,
    max_budget: float,
) -> bool:
    """
    deal = hard_constraints_pass AND (reserve_price <= proposed_payment <= max_budget)
    """
    return (
        hard_constraints_pass
        and reserve_price <= proposed_payment <= max_budget
    )


# ---------------------------------------------------------------------------
# Step 7: Orchestrator
# ---------------------------------------------------------------------------

def run_deterministic(
    dataset_id: str,
    policy: BuyerPolicy,
    reserve_price: float,
) -> dict[str, Any]:
    """
    Run the full deterministic evaluation for a single dataset.

    Returns a dict consumed by run_skill():
    {
        "metrics":           DatasetMetrics,
        "component_scores":  dict[str, float],
        "quality_score":     float,        # preliminary S (schema + claim are placeholders)
        "proposed_payment":  float,
        "deal":              bool,
        "notes":             list[str],    # human-readable partial-failure notes
    }
    """
    dataset = get_dataset(dataset_id)
    df: pd.DataFrame = dataset["df"]

    # Step 1
    metrics = compute_metrics(df, policy)

    # Step 2 — critical failures propagate directly to run_skill for early exit
    if metrics.critical_failure:
        return {
            "metrics": metrics,
            "component_scores": {},
            "quality_score": 0.0,
            "proposed_payment": policy.base_price,
            "deal": False,
            "notes": [metrics.critical_reason] if metrics.critical_reason else [],
        }

    # Step 3
    component_scores = compute_component_scores(metrics, policy)

    # Step 4
    quality_score = compute_quality_score(component_scores, policy)

    # Step 5
    proposed_payment = compute_price(quality_score, policy.base_price, policy.max_budget)

    # Step 6
    deal = check_deal(
        metrics.hard_constraints_pass, reserve_price, proposed_payment, policy.max_budget
    )

    # Build human-readable notes for partial failures (non-critical but notable)
    notes: list[str] = []

    if metrics.overall_null_rate > policy.max_null_rate:
        notes.append(
            f"Null rate ({metrics.overall_null_rate:.1%}) exceeds policy threshold "
            f"({policy.max_null_rate:.1%}). Quality score penalised."
        )

    if metrics.duplicate_rate > policy.max_duplicate_rate:
        notes.append(
            f"Duplicate rate ({metrics.duplicate_rate:.1%}) exceeds policy threshold "
            f"({policy.max_duplicate_rate:.1%}). Quality score penalised."
        )

    if metrics.row_count < policy.min_rows:
        notes.append(
            f"Row count ({metrics.row_count:,}) is below policy minimum "
            f"({policy.min_rows:,}). Coverage score penalised."
        )

    if (
        policy.min_label_rate is not None
        and metrics.label_rate is not None
        and metrics.label_rate < policy.min_label_rate
    ):
        notes.append(
            f"Label rate ({metrics.label_rate:.2%}) is below policy minimum "
            f"({policy.min_label_rate:.2%})."
        )

    if not deal and not metrics.critical_failure:
        if reserve_price > proposed_payment:
            notes.append(
                f"Proposed payment (${proposed_payment:,.2f}) is below supplier's "
                "reserve price. Consider renegotiation."
            )

    return {
        "metrics": metrics,
        "component_scores": component_scores,
        "quality_score": quality_score,
        "proposed_payment": proposed_payment,
        "deal": deal,
        "notes": notes,
    }
