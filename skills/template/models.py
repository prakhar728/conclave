"""
Input and output models for this skill.

TODO: Rename this file's classes and fields to match your domain.

Input model:
- Must extend Submission (which provides submission_id and optional metadata).
- Add fields the user submits (text, files, data, etc.).

Output model:
- Define all fields that appear in the skill's results.
- Every field name here MUST be listed in ALLOWED_OUTPUT_KEYS (config.py).
- Numeric fields MUST have a corresponding entry in SCORE_BOUNDS (config.py).
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from core.models import Submission


class TemplateSubmission(Submission):
    """User-submitted input. Extend Submission with your domain fields.

    Examples:
    - Hackathon: idea_text, repo_summary, deck_text
    - Salary eval: role, experience_years, location, expected_salary
    - Dataset audit: dataset_url, description, demographic_columns
    """
    # TODO: Replace these with your domain fields
    text_field: str = Field(description="Primary text input from the user")
    optional_field: Optional[str] = Field(default=None, description="Optional supporting data")


class TemplateResult(BaseModel):
    """Output for a single submission. All fields must be in ALLOWED_OUTPUT_KEYS.

    Examples:
    - Hackathon: novelty_score, percentile, criteria_scores, status
    - Salary eval: suggested_range_low, suggested_range_high, confidence, reasoning_summary
    - Dataset audit: bias_score, flagged_columns, severity
    """
    # TODO: Replace these with your output fields
    submission_id: str
    score: float = Field(ge=0.0, le=10.0, description="Primary score (0-10)")
    status: str = Field(default="scored", description="Processing status")
