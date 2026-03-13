from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class Submission(BaseModel):
    """Thin base — every skill input has at minimum a submission_id.
    Skills define their own subclass (e.g. HackathonSubmission) to add
    the fields they actually need.
    """
    submission_id: str
    metadata: Optional[dict] = None


class OperatorConfig(BaseModel):
    criteria: dict[str, float]  # e.g. {"originality": 0.4, "feasibility": 0.3, "impact": 0.3}
    guidelines: str = ""
    instance_id: str = "default"


class SkillRequest(BaseModel):
    skill_name: str
    inputs: list[dict]          # skill-specific input dicts, validated at invoke time
    params: OperatorConfig


class SkillResponse(BaseModel):
    skill: str
    results: list[dict]
    trace: Optional[list[dict]] = None
    enclave_signature: Optional[str] = None   # added by infra side
    attestation_quote: Optional[str] = None   # added by infra side
