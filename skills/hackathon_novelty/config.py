"""
Skill-specific constants for hackathon_novelty.

What to edit here:
- ALLOWED_OUTPUT_KEYS: add/remove keys that the guardrail whitelist and SkillCard expose
- SCORE_BOUNDS: change clamping ranges for numeric output fields
- MIN_LEAKAGE_SUBSTRING_LENGTH: tune leakage detection sensitivity
- MIN_SUBMISSIONS: minimum batch size for analysis to run
- SIMILARITY_DUPLICATE_THRESHOLD: guidance value passed to triage LLM prompt (not a hard cutoff)
- LOW_NOVELTY_THRESHOLD: guidance value passed to triage LLM prompt (not a hard cutoff)
- *_MODEL: per-node model overrides (set in skills/hackathon_novelty/.env)

Consumed by:
- guardrails.py (ALLOWED_OUTPUT_KEYS, SCORE_BOUNDS, MIN_LEAKAGE_SUBSTRING_LENGTH)
- __init__.py (MIN_SUBMISSIONS, ALLOWED_OUTPUT_KEYS via skill_card)
- agent.py (SIMILARITY_DUPLICATE_THRESHOLD, LOW_NOVELTY_THRESHOLD in triage prompt)
- agent.py + init.py (*_MODEL constants)
"""
import os
from dotenv import load_dotenv

# Load skill-specific env vars before reading them below.
# This file lives at skills/hackathon_novelty/.env (gitignored).
# Global .env only contains API keys and infrastructure config.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

ALLOWED_OUTPUT_KEYS = {
    "submission_id",
    "novelty_score",
    "relevance_score",
    "aligned",
    "criteria_scores",
    "status",
    "analysis_depth",
    "duplicate_of",
}

SCORE_BOUNDS = {
    "novelty_score": (0.0, 1.0),
    "relevance_score": (0.0, 1.0),
    "criteria_scores": (0.0, 10.0),
}

MIN_LEAKAGE_SUBSTRING_LENGTH = 20
MIN_SUBMISSIONS = 5

# Guidance values for the triage LLM prompt — NOT hard if-else thresholds.
# The LLM uses these as reference points but reasons about context (cluster size,
# material availability, similarity patterns) before making its classification decision.
SIMILARITY_DUPLICATE_THRESHOLD = 0.95
LOW_NOVELTY_THRESHOLD = 0.1

# Participant-facing output — only Conclave-unique signals.
# Admin sees ALLOWED_OUTPUT_KEYS (everything). Users see USER_OUTPUT_KEYS.
USER_OUTPUT_KEYS = {"submission_id", "novelty_score", "aligned"}

# Relevance threshold for the "aligned" boolean flag.
# Below this → aligned=False (submission doesn't match hackathon theme).
RELEVANCE_THRESHOLD = 0.15

# Per-node model overrides — set via CONCLAVE_*_MODEL env vars.
# Empty string falls back to CONCLAVE_DEFAULT_MODEL (or DeepSeek-V3.1 if unset).
_default = os.environ.get("CONCLAVE_DEFAULT_MODEL", "deepseek-ai/DeepSeek-V3.1")
INIT_MODEL    = os.environ.get("CONCLAVE_INIT_MODEL")    or _default
TRIAGE_MODEL  = os.environ.get("CONCLAVE_TRIAGE_MODEL")  or _default
QUICK_MODEL   = os.environ.get("CONCLAVE_QUICK_MODEL")   or _default
ANALYZE_MODEL = os.environ.get("CONCLAVE_ANALYZE_MODEL") or _default
