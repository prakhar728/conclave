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
from skills.hackathon_novelty.config import MIN_SUBMISSIONS


_SYSTEM_PROMPT = (
    "You are setting up a hackathon novelty evaluation instance. "
    "Your job is to collect the required configuration from the operator.\n\n"
    "REQUIRED:\n"
    "- criteria: a dict of criterion names to weights that sum to exactly 1.0\n"
    "  Example: {\"originality\": 0.4, \"feasibility\": 0.3, \"impact\": 0.3}\n\n"
    "OPTIONAL:\n"
    "- guidelines: free-text judging instructions (e.g. 'Focus on AI/ML projects')\n"
    f"- threshold: minimum submissions before auto-evaluation runs (default: {MIN_SUBMISSIONS})\n\n"
    "Ask for missing information conversationally. "
    "Once you have all required information, respond with ONLY this JSON and nothing else:\n"
    '{"ready": true, "criteria": {"name": weight, ...}, "guidelines": "...", "threshold": N}'
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
    Handle one turn of the operator onboarding conversation.

    Called by the API on each POST /init. The API passes the accumulated
    conversation; this handler appends the new messages and returns the result.
    """
    # Initialise conversation with system prompt on first turn
    if not conversation:
        conversation = [{"role": "system", "content": _SYSTEM_PROMPT}]

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

    llm = get_llm()
    response = llm.invoke(lc_messages)
    ai_text = response.content

    conversation = conversation + [{"role": "ai", "content": ai_text}]

    extracted = _parse_llm_response(ai_text)
    if extracted:
        criteria = extracted.get("criteria", {})
        guidelines = extracted.get("guidelines", "")
        threshold = int(extracted.get("threshold", MIN_SUBMISSIONS))
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
