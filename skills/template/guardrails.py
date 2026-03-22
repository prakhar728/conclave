"""
Output filter for this skill.

The guardrail pipeline (defined in core/guardrails.py) runs:
    filter_keys() -> check_bounds() -> leakage_check()

TODO: Update check_bounds() for your skill's numeric output fields.

- filter_keys() strips any keys not in ALLOWED_OUTPUT_KEYS (automatic).
- check_bounds() clamps numeric values to SCORE_BOUNDS ranges (you implement this).
- leakage_check() catches raw input substrings that leaked into output (automatic).
"""
from core.guardrails import OutputFilterBase, LeakageDetector
from skills.template.config import ALLOWED_OUTPUT_KEYS, SCORE_BOUNDS, MIN_LEAKAGE_SUBSTRING_LENGTH


class TemplateFilter(OutputFilterBase):
    def __init__(self):
        super().__init__(
            allowed_keys=ALLOWED_OUTPUT_KEYS,
            leakage_detector=LeakageDetector(min_length=MIN_LEAKAGE_SUBSTRING_LENGTH),
        )

    def check_bounds(self, result: dict) -> dict:
        """Clamp numeric scores to valid ranges. String fields pass through.

        TODO: Add clamping for each numeric field in your Result model.
        Pattern: if "field" in result: clamp to SCORE_BOUNDS["field"]
        """
        if "score" in result:
            lo, hi = SCORE_BOUNDS["score"]
            result["score"] = max(lo, min(hi, result["score"]))

        # TODO: Add more clamping as needed. Examples:
        # if "confidence" in result:
        #     lo, hi = SCORE_BOUNDS["confidence"]
        #     result["confidence"] = max(lo, min(hi, result["confidence"]))
        #
        # # For dict-of-scores (like criteria_scores):
        # if "criteria_scores" in result and isinstance(result["criteria_scores"], dict):
        #     lo, hi = SCORE_BOUNDS["criteria_scores"]
        #     result["criteria_scores"] = {
        #         k: max(lo, min(hi, v)) for k, v in result["criteria_scores"].items()
        #     }

        return result
