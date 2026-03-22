"""
Output filter and tool output validator for confidential_data_procurement.

ProcurementFilter — role-aware output filter:
  - Buyer (admin):      sees quality_score, hard_constraints_pass
  - Supplier (user):    those two fields are withheld (budget leak prevention —
                        if supplier sees quality_score + proposed_payment they can
                        compute max_budget = P / S)

validate_tool_output — programmatic guardrail wrapping every agent data tool:
  - Blocks raw row dumps   (too many CSV-like lines)
  - Blocks high-cardinality value lists (> MAX_TOOL_OUTPUT_ITEMS list entries)
  - Blocks oversized blobs (> MAX_TOOL_OUTPUT_CHARS)

LeakageDetector is applied inside ProcurementFilter.apply() (inherited from
OutputFilterBase). Even if the LLM echoes a cell value in its explanation, the
detector flags it before the response leaves the pipeline.
"""
from __future__ import annotations

from core.guardrails import LeakageDetector, OutputFilterBase
from skills.confidential_data_procurement.config import (
    ALLOWED_OUTPUT_KEYS,
    MIN_LEAKAGE_SUBSTRING_LENGTH,
    SCORE_BOUNDS,
    USER_OUTPUT_KEYS,
)

# ---------------------------------------------------------------------------
# Tool output guardrail constants
# ---------------------------------------------------------------------------

MAX_TOOL_OUTPUT_CHARS: int = 4_000
MAX_TOOL_OUTPUT_ITEMS: int = 50   # max enumerated items (bullet/colon lines)
MAX_RAW_ROW_LINES:     int = 5    # more comma-separated lines than this → raw dump


# ---------------------------------------------------------------------------
# Role-aware output filter
# ---------------------------------------------------------------------------

class ProcurementFilter(OutputFilterBase):
    """
    Role-aware output filter for the dataset procurement pipeline.

    role="admin"  → buyer view  — full ALLOWED_OUTPUT_KEYS (includes quality_score)
    role="user"   → supplier view — USER_OUTPUT_KEYS (quality_score withheld)
    """

    def __init__(self, role: str = "admin"):
        keys = ALLOWED_OUTPUT_KEYS if role == "admin" else USER_OUTPUT_KEYS
        super().__init__(
            allowed_keys=keys,
            leakage_detector=LeakageDetector(min_length=MIN_LEAKAGE_SUBSTRING_LENGTH),
        )

    def check_bounds(self, result: dict) -> dict:
        """Clamp quality_score to [0, 1]. All other fields pass through."""
        if "quality_score" in result:
            lo, hi = SCORE_BOUNDS["quality_score"]
            result["quality_score"] = max(lo, min(hi, float(result["quality_score"])))
        return result


# ---------------------------------------------------------------------------
# Tool output validator
# ---------------------------------------------------------------------------

def validate_tool_output(output: str) -> str:
    """
    Programmatic guardrail for every agent data tool.

    Raises ValueError if the output looks like:
      - A raw row dump   (> MAX_RAW_ROW_LINES CSV-like lines)
      - A high-cardinality list (> MAX_TOOL_OUTPUT_ITEMS enumerated items)
      - An oversized blob (> MAX_TOOL_OUTPUT_CHARS characters)

    Returns the output unchanged if all checks pass.
    """
    if len(output) > MAX_TOOL_OUTPUT_CHARS:
        raise ValueError(
            f"Tool output too large ({len(output):,} chars). "
            f"Maximum allowed: {MAX_TOOL_OUTPUT_CHARS:,}. "
            "Return aggregate statistics, not raw data."
        )

    lines = [line for line in output.splitlines() if line.strip()]

    # Raw row detection — a real stats summary rarely has many comma-heavy lines
    csv_like = sum(1 for line in lines if line.count(",") >= 2)
    if csv_like > MAX_RAW_ROW_LINES:
        raise ValueError(
            f"Tool output contains {csv_like} CSV-like lines "
            f"(threshold: {MAX_RAW_ROW_LINES}). "
            "Tools must return aggregate statistics, not raw rows."
        )

    # High-cardinality detection — count bullet/label lines
    list_items = [
        line for line in lines
        if line.lstrip().startswith(("-", "*", "•")) or ": " in line
    ]
    if len(list_items) > MAX_TOOL_OUTPUT_ITEMS:
        raise ValueError(
            f"Tool output enumerates {len(list_items)} items "
            f"(threshold: {MAX_TOOL_OUTPUT_ITEMS}). "
            "Return top-N values or aggregates only."
        )

    return output
