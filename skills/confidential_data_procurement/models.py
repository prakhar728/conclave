"""
Input and output Pydantic models for the confidential_data_procurement skill.

Roles:
- BuyerPolicy:         operator config — replaces OperatorConfig for this skill.
                       NEVER expose max_budget or base_price to the supplier.
- SupplierSubmission:  participant input — references an uploaded dataset by ID.
                       NEVER expose reserve_price to the buyer.
- DatasetMetrics:      intermediate deterministic output — not returned to API callers.
- ProcurementResult:   final result per submission — key-filtered by role in routes.py.
                       revised_budget / revised_reserve are internal-only fields,
                       excluded from both ALLOWED_OUTPUT_KEYS and USER_OUTPUT_KEYS.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from core.models import Submission


class BuyerPolicy(BaseModel):
    """
    Operator config for the confidential_data_procurement skill.
    Extracted by the init_handler from the buyer's onboarding conversation.
    routes.py sets instance_id after init completes.
    """
    required_columns: list[str]               # semantic — agent does fuzzy matching
    min_rows: int = Field(gt=0)
    max_null_rate: float = Field(ge=0.0, le=1.0)       # e.g. 0.03 = 3%
    max_duplicate_rate: float = Field(ge=0.0, le=1.0)
    min_label_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    label_column: Optional[str] = None
    forbidden_columns: list[str] = []
    max_budget: float = Field(gt=0.0)          # NEVER exposed to supplier
    base_price: float = Field(default=0.0, ge=0.0)    # floor: P when S=0
    score_weights: dict[str, float] = {}       # buyer overrides DEFAULT_SCORE_WEIGHTS
    description: str = ""                      # natural language description of dataset need
    instance_id: str = "default"               # set by routes.py after init

    @model_validator(mode="after")
    def validate_weights(self) -> "BuyerPolicy":
        if self.score_weights:
            total = sum(self.score_weights.values())
            if abs(total - 1.0) > 0.01:
                raise ValueError(
                    f"score_weights must sum to 1.0 (got {total:.3f}). "
                    "Adjust weights or omit to use defaults."
                )
        if self.base_price >= self.max_budget:
            raise ValueError("base_price must be less than max_budget")
        return self


class SupplierSubmission(Submission):
    """
    Participant input for the confidential_data_procurement skill.
    Supplier uploads their dataset via POST /upload first, then submits here.
    """
    dataset_id: str                # references uploaded DataFrame in ingest store
    dataset_name: str
    reserve_price: float = Field(ge=0.0)   # NEVER exposed to buyer


class DatasetMetrics(BaseModel):
    """
    Deterministic quality metrics computed from the raw DataFrame.
    Intermediate result — never returned directly to API callers.
    """
    row_count: int
    column_names: list[str]
    null_rate_by_column: dict[str, float]
    overall_null_rate: float
    duplicate_rate: float
    label_rate: Optional[float] = None           # None if label_column not specified
    forbidden_columns_present: list[str] = []
    hard_constraints_pass: bool                  # all binary must-pass checks
    critical_failure: bool = False               # triggers early exit before agent
    critical_reason: Optional[str] = None        # human-readable reason for critical failure


class ProcurementResult(BaseModel):
    """
    Final result per submission after guardrails.
    Role-filtered in routes.py: buyer sees ALLOWED_OUTPUT_KEYS, supplier sees USER_OUTPUT_KEYS.

    Field notes:
    - deal:                 enclave's mathematical verdict (R ≤ P ≤ B and hard constraints pass)
    - quality_score:        buyer-only — supplier could reverse-engineer max_budget via P/S
    - hard_constraints_pass: buyer-only — same reasoning
    - settlement_status:    lifecycle state — independent of deal bool
                            "rejected" | "pending_approval" | "awaiting_counterparty" |
                            "renegotiating" | "authorized"
    - revised_budget/reserve: INTERNAL — never in any output key set
    """
    submission_id: str
    deal: bool = False
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)   # buyer-only
    proposed_payment: float = 0.0
    hard_constraints_pass: bool = False                           # buyer-only
    settlement_status: Literal[
        "rejected",
        "pending_approval",
        "awaiting_counterparty",
        "renegotiating",
        "authorized",
    ] = "rejected"
    release_token: Optional[str] = None
    notes: list[str] = []                         # failure/partial notes — same for both roles
    explanation: Optional[str] = None             # bounded LLM summary
    claim_verification: Optional[dict[str, Any]] = None   # from agent layer
    schema_matching: Optional[dict[str, Any]] = None      # from agent layer
    buyer_response: Optional[Literal["accept", "reject", "renegotiate"]] = None
    supplier_response: Optional[Literal["accept", "reject", "renegotiate"]] = None
    renegotiation_used: bool = False

    # INTERNAL ONLY — excluded from ALLOWED_OUTPUT_KEYS and USER_OUTPUT_KEYS
    revised_budget: Optional[float] = None
    revised_reserve: Optional[float] = None
