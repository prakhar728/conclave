"""
Input and output Pydantic models for the hackathon_novelty skill.

What to edit here:
- HackathonSubmission: add new input fields a submitter provides (e.g., video_url, team_size)
- NoveltyResult: add new output fields the pipeline produces after guardrails

HackathonSubmission extends the thin core.Submission base (submission_id + metadata).
NoveltyResult is what the guardrail layer produces — only fields in ALLOWED_OUTPUT_KEYS survive.
Adding a field here AND to config.ALLOWED_OUTPUT_KEYS makes it flow through to the API response.
"""
from __future__ import annotations
from typing import Optional

from pydantic import BaseModel, Field

from core.models import Submission


class HackathonSubmission(Submission):
    """Input model for the hackathon_novelty skill."""
    idea_text: str
    repo_summary: Optional[str] = None
    deck_text: Optional[str] = None


class NoveltyResult(BaseModel):
    """Final output for one submission after guardrails. This is what leaves the skill."""
    submission_id: str
    novelty_score: float = Field(ge=0.0, le=1.0)
    relevance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    aligned: Optional[bool] = None
    criteria_scores: dict[str, float] = {}
    # Analysis metadata — set by the agent based on which branch processed this submission
    status: str = "analyzed"          # "analyzed" | "duplicate" | "quick_scored"
    analysis_depth: str = "full"      # "full" | "quick" | "flagged"
    duplicate_of: Optional[str] = None  # submission_id of the original if status="duplicate"
