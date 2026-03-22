"""
Buyer onboarding handler for confidential_data_procurement.

The API calls procurement_init_handler(message, conversation) on each POST /init.
This module owns all procurement-specific onboarding logic:
  - Greeting and guided data-collection conversation
  - LLM extraction of BuyerPolicy fields from free-form buyer input
  - BuyerPolicy construction and validation

Handler interface (same contract as hackathon_novelty.init):
    procurement_init_handler(message: str, conversation: list[dict]) -> dict

    Returns one of:
      {"status": "configuring", "message": str, "conversation": list[dict]}
      {"status": "ready",       "message": str, "conversation": list[dict],
       "config": BuyerPolicy,   "threshold": 1}

threshold is always 1 — procurement triggers instantly when a supplier submits.
"""
from __future__ import annotations

import json
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config import get_llm
from skills.confidential_data_procurement.config import INIT_MODEL
from skills.confidential_data_procurement.models import BuyerPolicy


INIT_PROMPT_VERSION = "v1"


_GREETING_TEMPLATE = """\
Welcome to the Confidential Data Procurement setup.

I'll help you configure your dataset acquisition policy inside the TEE. \
Suppliers will upload datasets and submit a reserve price — neither party \
sees the other's private numbers.

Please provide the following:

**Required**
1. **Dataset description** — what kind of data you need and why
2. **Required columns** — list the column names you expect
   Example: transaction_id, amount, is_fraud
3. **Minimum rows** — fewest acceptable rows (e.g. 10000)
4. **Max null rate** — e.g. 5% means at most 5% cells can be missing
5. **Max duplicate rate** — e.g. 10% means at most 10% duplicate rows
6. **Maximum budget** — the most you will pay for a perfect dataset ($)

**Optional**
- **Base price** — minimum payment even for poor-quality data (default $0)
- **Label column** + **minimum label rate** — e.g. is_fraud column must have ≥ 2% positives
- **Forbidden columns** — PII fields to block (e.g. ssn, dob, passport_number)

You can provide everything in one message or answer step by step.\
"""


_SYSTEM_PROMPT = """\
You are configuring a confidential dataset procurement instance for a buyer. \
Your job is to collect the required policy fields from the buyer's messages.

REQUIRED fields (must be present and valid before responding with JSON):
  - required_columns: list of expected column name strings (non-empty)
  - min_rows: positive integer
  - max_null_rate: float in [0, 1]  (e.g. 0.05 for 5%)
  - max_duplicate_rate: float in [0, 1]
  - max_budget: positive float (the ceiling payment for a perfect dataset)

OPTIONAL fields (use defaults if not provided):
  - base_price: float >= 0, default 0.0  (floor payment when quality score = 0)
  - min_label_rate: float in [0, 1] or null
  - label_column: string or null
  - forbidden_columns: list of strings, default []
  - description: free-text description of the dataset need

CRITICAL RULE: base_price must be strictly less than max_budget. \
If the buyer provides both and base_price >= max_budget, ask them to fix it.

Once you have all required fields and they are valid, respond with ONLY this \
JSON — no extra text, no markdown fences:
{
  "ready": true,
  "required_columns": [...],
  "min_rows": N,
  "max_null_rate": 0.XX,
  "max_duplicate_rate": 0.XX,
  "max_budget": NNN.0,
  "base_price": NN.0,
  "min_label_rate": null_or_float,
  "label_column": null_or_string,
  "forbidden_columns": [...],
  "description": "..."
}

Only ask follow-up questions if required fields are missing or invalid. \
Convert percentages to decimals (e.g. "5%" → 0.05).\
"""


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


def procurement_init_handler(message: str, conversation: list[dict]) -> dict:
    """
    Handle one turn of the buyer onboarding conversation.

    Called by the API on each POST /init. The accumulated conversation is passed
    in; this handler appends the new messages and returns the updated state.
    """
    # First turn: return fixed greeting immediately (no LLM call).
    if not conversation:
        conversation = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "ai",     "content": _GREETING_TEMPLATE},
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
    if not extracted:
        return {
            "status": "configuring",
            "message": ai_text,
            "conversation": conversation,
        }

    # Validate required fields
    required_columns = extracted.get("required_columns")
    if not required_columns or not isinstance(required_columns, list):
        return {
            "status": "configuring",
            "message": "Required columns cannot be empty. Please list the column names you expect.",
            "conversation": conversation,
        }

    min_rows = extracted.get("min_rows")
    try:
        min_rows = int(min_rows)
        if min_rows < 1:
            raise ValueError
    except (TypeError, ValueError):
        return {
            "status": "configuring",
            "message": "Minimum rows must be a positive integer. Please provide a valid number.",
            "conversation": conversation,
        }

    max_budget = extracted.get("max_budget")
    try:
        max_budget = float(max_budget)
        if max_budget <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return {
            "status": "configuring",
            "message": "Maximum budget must be a positive number. Please provide a valid dollar amount.",
            "conversation": conversation,
        }

    for rate_key in ("max_null_rate", "max_duplicate_rate"):
        val = extracted.get(rate_key)
        try:
            val = float(val)
            if not (0.0 <= val <= 1.0):
                raise ValueError
        except (TypeError, ValueError):
            return {
                "status": "configuring",
                "message": (
                    f"{rate_key.replace('_', ' ').title()} must be a decimal between 0 and 1 "
                    "(e.g. 0.05 for 5%). Please provide a valid value."
                ),
                "conversation": conversation,
            }

    base_price = float(extracted.get("base_price") or 0.0)
    if base_price >= max_budget:
        return {
            "status": "configuring",
            "message": (
                f"Base price (${base_price:,.2f}) must be less than max budget (${max_budget:,.2f}). "
                "Please adjust."
            ),
            "conversation": conversation,
        }

    # Build and validate BuyerPolicy (Pydantic catches anything we missed)
    try:
        policy = BuyerPolicy(
            required_columns=[str(c) for c in required_columns],
            min_rows=min_rows,
            max_null_rate=float(extracted["max_null_rate"]),
            max_duplicate_rate=float(extracted["max_duplicate_rate"]),
            min_label_rate=extracted.get("min_label_rate"),
            label_column=extracted.get("label_column"),
            forbidden_columns=[str(c) for c in (extracted.get("forbidden_columns") or [])],
            max_budget=max_budget,
            base_price=base_price,
            description=str(extracted.get("description") or ""),
        )
    except Exception as exc:
        return {
            "status": "configuring",
            "message": f"Could not build policy: {exc}. Please review your inputs.",
            "conversation": conversation,
        }

    ready_message = (
        f"Policy saved.\n"
        f"Required columns: {', '.join(policy.required_columns)}\n"
        f"Minimum rows: {policy.min_rows:,}\n"
        f"Max null rate: {policy.max_null_rate:.0%}  |  "
        f"Max duplicate rate: {policy.max_duplicate_rate:.0%}\n"
        f"Budget: ${policy.base_price:,.2f} – ${policy.max_budget:,.2f}\n"
        + (f"Label column: {policy.label_column} (≥ {policy.min_label_rate:.1%})\n"
           if policy.label_column and policy.min_label_rate is not None else "")
        + (f"Forbidden columns: {', '.join(policy.forbidden_columns)}\n"
           if policy.forbidden_columns else "")
        + "\nShare the instance link with your supplier to begin."
    )

    return {
        "status": "ready",
        "message": ready_message,
        "conversation": conversation,
        "config": policy,
        "threshold": 1,     # procurement triggers instantly on first supplier submission
    }
