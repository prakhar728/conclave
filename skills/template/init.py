"""
Operator onboarding handler.

The API calls init_handler(message, conversation) on each POST /init request.
This module manages the conversational setup with the admin/operator.

Handler interface:
    init_handler(message: str, conversation: list[dict]) -> dict
    Returns:
        {"status": "configuring", "message": str, "conversation": list[dict]}
        {"status": "ready", "message": str, "conversation": list[dict],
         "config": OperatorConfig, "threshold": int}

TODO:
- Customize _SYSTEM_PROMPT for your skill's configuration needs
- Update validation logic for your required fields
- If your skill doesn't need admin setup, set init_handler=None in the SkillCard
"""
from __future__ import annotations
import json
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from config import get_llm
from core.models import OperatorConfig
from skills.template.config import MIN_SUBMISSIONS, INIT_MODEL


INIT_PROMPT_VERSION = "v1"


# TODO: Customize this prompt for your skill's configuration needs.
# The LLM collects config from the admin and outputs JSON when ready.
# Key pattern: be explicit about what JSON to output when done.
_SYSTEM_PROMPT = (
    "You are setting up an evaluation instance for a new skill. "
    "Your job is to collect the required configuration from the admin.\n\n"
    "REQUIRED:\n"
    "- criteria: a dict of criterion names to weights that sum to exactly 1.0\n"
    '  Example: {"quality": 0.5, "relevance": 0.3, "clarity": 0.2}\n\n'
    "OPTIONAL:\n"
    "- guidelines: free-text instructions for the evaluation agent\n"
    f"- threshold: minimum submissions before auto-evaluation runs (default: {MIN_SUBMISSIONS})\n\n"
    "IMPORTANT: As soon as you have the required criteria (with weights summing to 1.0), "
    "respond with ONLY the JSON below — no confirmation, no commentary, no extra text:\n"
    '{"ready": true, "criteria": {"name": weight, ...}, "guidelines": "...", "threshold": N}\n\n'
    "Only ask follow-up questions if the criteria are missing or weights do not sum to 1.0."
)


def _parse_llm_response(text: str) -> Optional[dict]:
    """Strip markdown fences, parse JSON, return dict if ready=true else None."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and obj.get("ready") is True:
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def template_init_handler(message: str, conversation: list[dict]) -> dict:
    """Handle one turn of the admin onboarding conversation."""
    if not conversation:
        conversation = [{"role": "system", "content": _SYSTEM_PROMPT}]

    conversation = conversation + [{"role": "human", "content": message}]

    lc_messages = []
    for msg in conversation:
        if msg["role"] == "system":
            lc_messages.append(SystemMessage(content=msg["content"]))
        elif msg["role"] == "human":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AIMessage(content=msg["content"]))

    llm = get_llm(INIT_MODEL)
    response = llm.invoke(lc_messages)
    ai_text = response.content

    conversation = conversation + [{"role": "ai", "content": ai_text}]

    extracted = _parse_llm_response(ai_text)
    if extracted:
        criteria = extracted.get("criteria", {})
        guidelines = extracted.get("guidelines", "")

        if not criteria:
            return {
                "status": "configuring",
                "message": "Criteria cannot be empty. Please provide at least one criterion with a weight.",
                "conversation": conversation,
            }

        weight_sum = sum(criteria.values())
        if abs(weight_sum - 1.0) > 0.01:
            return {
                "status": "configuring",
                "message": f"Criteria weights must sum to 1.0 (got {weight_sum:.2f}). Please adjust.",
                "conversation": conversation,
            }

        try:
            threshold = int(extracted.get("threshold", MIN_SUBMISSIONS))
            if threshold < 1:
                raise ValueError("non-positive")
        except (ValueError, TypeError):
            return {
                "status": "configuring",
                "message": "Threshold must be a positive integer.",
                "conversation": conversation,
            }

        config = OperatorConfig(criteria=criteria, guidelines=guidelines)
        return {
            "status": "ready",
            "message": ai_text,
            "conversation": conversation,
            "config": config,
            "threshold": threshold,
        }

    return {
        "status": "configuring",
        "message": ai_text,
        "conversation": conversation,
    }
