"""
Operator onboarding handler for hackathon_novelty.

The API calls init_handler(message, conversation) on each /init request.
This module owns all hackathon-specific onboarding logic:
- System prompt construction (criteria weights, guidelines, threshold)
- LLM conversation management
- JSON extraction and OperatorConfig construction

To adapt for a different skill: implement a new handler with the same
interface. The API doesn't care what happens inside.

Handler interface:
    init_handler(message: str, conversation: list[dict]) -> dict
    Returns:
        {"status": "configuring", "message": str, "conversation": list[dict]}
        {"status": "ready", "message": str, "conversation": list[dict],
         "config": OperatorConfig, "threshold": int}
"""
from __future__ import annotations
import json
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from config import get_llm
from core.models import OperatorConfig
from skills.hackathon_novelty.config import MIN_SUBMISSIONS, INIT_MODEL


# Bump when changing _SYSTEM_PROMPT or _GREETING_TEMPLATE.
INIT_PROMPT_VERSION = "v3"


_GREETING_TEMPLATE = (
    "Welcome to hackathon evaluation setup.\n\n"
    "Please provide the following:\n\n"
    "1. **Evaluation criteria** with weights summing to 1.0\n"
    '   Example: {"originality": 0.4, "feasibility": 0.3, "impact": 0.3}\n\n'
    "2. **(Optional) Guidelines** — judging instructions\n"
    '   Example: "Focus on AI/ML innovations"\n\n'
    f"3. **(Optional) Threshold** — minimum submissions before auto-evaluation (default: {MIN_SUBMISSIONS})\n\n"
    "You can provide everything in one message."
)


_SYSTEM_PROMPT = (
    "You are setting up a hackathon novelty evaluation instance. "
    "Your job is to collect the required configuration from the admin.\n\n"
    "REQUIRED:\n"
    "- criteria: a dict of criterion names to weights that sum to exactly 1.0\n"
    "  Example: {\"originality\": 0.4, \"feasibility\": 0.3, \"impact\": 0.3}\n\n"
    "OPTIONAL:\n"
    "- guidelines: free-text judging instructions (e.g. 'Focus on AI/ML projects')\n"
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


def hackathon_init_handler(message: str, conversation: list[dict]) -> dict:
    """
    Handle one turn of the admin onboarding conversation.

    Called by the API on each POST /init. The API passes the accumulated
    conversation; this handler appends the new messages and returns the result.
    """
    # First turn: return fixed greeting immediately (no LLM call).
    # Seed the conversation so DeepSeek sees the greeting as its own message on turn 2+.
    if not conversation:
        conversation = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "ai", "content": _GREETING_TEMPLATE},
        ]
        return {
            "status": "configuring",
            "message": _GREETING_TEMPLATE,
            "conversation": conversation,
        }

    conversation = conversation + [{"role": "human", "content": message}]

    # Build LangChain messages
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
                "message": "Threshold must be a positive integer. Please provide a valid number.",
                "conversation": conversation,
            }

        config = OperatorConfig(criteria=criteria, guidelines=guidelines)
        ready_message = (
            f"Configuration saved.\n"
            f"Criteria: {json.dumps(criteria)}\n"
            f"Guidelines: {guidelines or '(none)'}\n"
            f"Threshold: {threshold} submissions"
        )
        return {
            "status": "ready",
            "message": ready_message,
            "conversation": conversation,
            "config": config,
            "threshold": threshold,
        }

    return {
        "status": "configuring",
        "message": ai_text,
        "conversation": conversation,
    }
