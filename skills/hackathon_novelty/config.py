"""
Skill-specific constants for hackathon_novelty.

What to edit here:
- ALLOWED_OUTPUT_KEYS: add/remove keys that the guardrail whitelist and SkillCard expose
- SCORE_BOUNDS: change clamping ranges for numeric output fields
- MIN_LEAKAGE_SUBSTRING_LENGTH: tune leakage detection sensitivity
- MIN_SUBMISSIONS: minimum batch size for analysis to run
- SIMILARITY_DUPLICATE_THRESHOLD: guidance value passed to triage LLM prompt (not a hard cutoff)
- LOW_NOVELTY_THRESHOLD: guidance value passed to triage LLM prompt (not a hard cutoff)

Consumed by:
- guardrails.py (ALLOWED_OUTPUT_KEYS, SCORE_BOUNDS, MIN_LEAKAGE_SUBSTRING_LENGTH)
- __init__.py (MIN_SUBMISSIONS, ALLOWED_OUTPUT_KEYS via skill_card)
- agent.py (SIMILARITY_DUPLICATE_THRESHOLD, LOW_NOVELTY_THRESHOLD in triage prompt)
"""

ALLOWED_OUTPUT_KEYS = {
    "submission_id",
    "novelty_score",
    "percentile",
    "cluster",
    "criteria_scores",
    "status",
    "analysis_depth",
    "duplicate_of",
}

SCORE_BOUNDS = {
    "novelty_score": (0.0, 1.0),
    "percentile": (0.0, 100.0),
    "criteria_scores": (0.0, 10.0),
}

MIN_LEAKAGE_SUBSTRING_LENGTH = 20
MIN_SUBMISSIONS = 5

# Guidance values for the triage LLM prompt — NOT hard if-else thresholds.
# The LLM uses these as reference points but reasons about context (cluster size,
# material availability, similarity patterns) before making its classification decision.
SIMILARITY_DUPLICATE_THRESHOLD = 0.95
LOW_NOVELTY_THRESHOLD = 0.1
