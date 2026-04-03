from __future__ import annotations
import uuid
from pydantic import BaseModel, Field
from typing import Optional


class Submission(BaseModel):
    """Thin base — every skill input has at minimum a submission_id.
    Skills define their own subclass (e.g. HackathonSubmission) to add
    the fields they actually need.
    """
    submission_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Optional[dict] = None


class OperatorConfig(BaseModel):
    criteria: dict[str, float]  # e.g. {"originality": 0.4, "feasibility": 0.3, "impact": 0.3}
    guidelines: str = ""
    instance_id: str = "default"
    min_submissions: int = 5


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


class InitRequest(BaseModel):
    skill_name: str
    message: str                        # admin's configuration message
    instance_id: Optional[str] = None   # None on first call, set on subsequent calls


class InitResponse(BaseModel):
    instance_id: str
    status: str                              # "configuring" | "ready"
    message: str                             # LLM response (question or confirmation)
    admin_token: Optional[str] = None     # only when status="ready"
