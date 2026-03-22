"""
Skill-specific constants.

TODO: Update these for your skill's output fields and thresholds.

Consumed by:
- guardrails.py  (ALLOWED_OUTPUT_KEYS, SCORE_BOUNDS, MIN_LEAKAGE_SUBSTRING_LENGTH)
- __init__.py    (MIN_SUBMISSIONS, ALLOWED_OUTPUT_KEYS via skill_card)
- tools.py       (*_MODEL constants for per-node model overrides)
"""
import os
from dotenv import load_dotenv

# Load skill-specific env vars (e.g., skills/template/.env, gitignored)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# --- Security whitelist ---
# ONLY these keys pass through the guardrail layer into API responses.
# Every field in your Result model must be listed here.
ALLOWED_OUTPUT_KEYS = {
    "submission_id",
    "score",
    "status",
    # TODO: Add your output fields here
}

# --- Numeric bounds for clamping ---
# Every numeric output field needs a (min, max) range.
# The guardrail layer clamps values to these bounds before returning results.
SCORE_BOUNDS = {
    "score": (0.0, 10.0),
    # TODO: Add bounds for your numeric fields
    # "confidence": (0.0, 1.0),
    # "criteria_scores": (0.0, 10.0),  # applied per-value for dicts
}

# --- Leakage detection ---
# Minimum substring length that triggers leakage detection.
# Lower = more sensitive (catches shorter leaked fragments).
# 20 is a good default for text-heavy inputs.
MIN_LEAKAGE_SUBSTRING_LENGTH = 20

# --- Pipeline thresholds ---
# Minimum number of submissions before the pipeline runs.
MIN_SUBMISSIONS = 3

# --- Per-node model overrides ---
# Set via env vars: CONCLAVE_DEFAULT_MODEL, CONCLAVE_INIT_MODEL, etc.
# Falls back to the global default model if not set.
_default = os.environ.get("CONCLAVE_DEFAULT_MODEL", "deepseek-ai/DeepSeek-V3.1")
INIT_MODEL = os.environ.get("CONCLAVE_INIT_MODEL") or _default
# TODO: Add per-node model overrides if your skill has multiple LLM nodes
# TRIAGE_MODEL  = os.environ.get("CONCLAVE_TRIAGE_MODEL")  or _default
# ANALYZE_MODEL = os.environ.get("CONCLAVE_ANALYZE_MODEL") or _default
