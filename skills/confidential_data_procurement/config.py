"""
Skill-specific constants for confidential_data_procurement.

What to edit here:
- ALLOWED_OUTPUT_KEYS:      buyer (admin) view — keys that leave the pipeline to the buyer
- USER_OUTPUT_KEYS:         supplier (participant) view — subset of ALLOWED_OUTPUT_KEYS.
                            quality_score and hard_constraints_pass are buyer-only to prevent
                            the supplier from reverse-engineering max_budget via P/S = max_budget.
- SCORE_BOUNDS:             clamping ranges for numeric output fields
- DEFAULT_SCORE_WEIGHTS:    used when buyer doesn't specify score_weights in BuyerPolicy
- CRITICAL_*:               deterministic early-exit thresholds (no LLM runs on critical failure)
- *_MODEL:                  per-node model overrides (set in .env)

Consumed by:
- deterministic.py  (CRITICAL_*, DEFAULT_SCORE_WEIGHTS)
- guardrails.py     (ALLOWED_OUTPUT_KEYS, USER_OUTPUT_KEYS, SCORE_BOUNDS)
- __init__.py       (ALLOWED_OUTPUT_KEYS, USER_OUTPUT_KEYS via skill_card)
- agent.py          (EVALUATE_MODEL)
- init.py           (INIT_MODEL)
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# --- Output key sets ---

# Buyer (admin) sees quality details + budget-sensitive fields
ALLOWED_OUTPUT_KEYS: set[str] = {
    "submission_id",
    "deal",
    "quality_score",           # buyer-only (budget leak if supplier sees this + proposed_payment)
    "proposed_payment",
    "hard_constraints_pass",   # buyer-only
    "settlement_status",
    "release_token",
    "notes",
    "explanation",
    "claim_verification",
    "schema_matching",
    "buyer_response",
    "supplier_response",
    "renegotiation_used",
}

# Supplier (participant) — same info, quality_score and hard_constraints_pass withheld
USER_OUTPUT_KEYS: set[str] = {
    "submission_id",
    "deal",
    "proposed_payment",
    "settlement_status",
    "release_token",
    "notes",
    "explanation",
    "claim_verification",
    "schema_matching",
    "buyer_response",
    "supplier_response",
    "renegotiation_used",
}

# --- Score bounds (used by guardrails for clamping) ---

SCORE_BOUNDS: dict[str, tuple[float, float]] = {
    "quality_score": (0.0, 1.0),
}

# --- Default score weights ---
# Buyer can override via BuyerPolicy.score_weights. Must sum to 1.0.
DEFAULT_SCORE_WEIGHTS: dict[str, float] = {
    "schema":         0.15,
    "coverage":       0.15,
    "null":           0.20,
    "duplicate":      0.15,
    "label":          0.10,
    "risk":           0.15,
    "claim_veracity": 0.10,
}

# --- Critical failure thresholds (deterministic early exit, no LLM) ---

# Duplicate rate above this → critical failure, deal rejected immediately
CRITICAL_DUPLICATE_THRESHOLD: float = 0.50

# Dataset size limits
MAX_DATASET_SIZE_MB: int = 50
MAX_DATASET_ROWS: int = 500_000

# Minimum leakage substring length passed to LeakageDetector
MIN_LEAKAGE_SUBSTRING_LENGTH: int = 20

# --- Per-node model overrides ---

_default = os.environ.get("CONCLAVE_DEFAULT_MODEL", "deepseek-ai/DeepSeek-V3.1")
INIT_MODEL     = os.environ.get("CONCLAVE_CDP_INIT_MODEL")     or _default
EVALUATE_MODEL = os.environ.get("CONCLAVE_CDP_EVALUATE_MODEL") or _default
