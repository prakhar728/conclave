"""
Single evaluate_node agent for confidential_data_procurement.

Graph: StateGraph with single evaluate_node → END.
Provides LangSmith trace visibility with proper node names, tool calls, and timing.

The dataset never leaves the TEE — the LLM sees only aggregate statistics
returned by the tools. validate_tool_output() in tools.py blocks raw row dumps.

Graph:
    evaluate_node (LLM + tools) → END
"""
from __future__ import annotations

import json
import re
from typing import Any, Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from config import get_llm
from skills.confidential_data_procurement.config import EVALUATE_MODEL
from skills.confidential_data_procurement.models import BuyerPolicy, DatasetMetrics
from skills.confidential_data_procurement.tools import EVALUATE_TOOLS, set_context


EVALUATE_PROMPT_VERSION = "v1"


_SYSTEM_PROMPT = """\
You are a data quality evaluator running inside a Trusted Execution Environment (TEE).
Your job is to assess a supplier's dataset against a buyer's acquisition policy.

You have three tools:
  - get_schema_summary()               — column names, dtypes, null rates, row count
  - get_column_stats(column_name)      — per-column statistics
  - get_value_distribution(column_name, top_n) — top-N value frequencies

TASK 1 — SCHEMA MATCHING
The buyer requires these columns (semantic — names may differ from actual dataset):
{required_columns}

Column definitions provided by the seller:
{column_definitions}

For each required column, find the best matching actual column.
A match is valid if the column names are semantically equivalent
(e.g. "transaction_id" ≈ "txn_id", "is_fraud" ≈ "fraud_label").
Score schema_score as: matched_count / required_count (0.0 if none match, 1.0 if all match).

TASK 2 — CLAIM VERIFICATION
The seller claims:
{seller_claims}

Call get_column_stats or get_value_distribution to check each claim against real data.
Mark each claim as "verified", "disputed", or "unverifiable" (if no relevant column exists).
Score claim_veracity_score as: verified_count / total_claims (1.0 if no claims).

TASK 3 — EXPLANATION
Write a concise (3-5 sentence) neutral explanation covering:
- Which required columns were found/missing
- Whether seller's claims held up
- Any notable quality concerns from the deterministic metrics

IMPORTANT:
- Only use aggregate stats from tools — never infer individual values
- Do not mention the buyer's budget, base price, or quality score
- Keep explanation under 400 words

After calling the tools you need, output ONLY this JSON (no markdown fences, no prose):
{{
  "schema_score": 0.0-1.0,
  "claim_veracity_score": 0.0-1.0,
  "schema_matching": {{"required_col": "matched_col_or_null", ...}},
  "claim_verification": {{"claim_text": "verified|disputed|unverifiable", ...}},
  "explanation": "..."
}}
"""


class EvaluateState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    dataset_id: str
    policy: Any       # BuyerPolicy — held in-memory, not serialized
    metrics: Any      # DatasetMetrics — held in-memory, not serialized
    eval_result: dict


# --- Node ---

def evaluate_node(state: EvaluateState) -> dict:
    """LLM node: schema matching + claim verification + explanation with tool loop."""
    from skills.confidential_data_procurement.ingest import get_dataset

    dataset_id = state["dataset_id"]
    policy: BuyerPolicy = state["policy"]
    metrics: DatasetMetrics = state["metrics"]

    dataset = get_dataset(dataset_id)
    column_definitions = dataset.get("column_definitions") or {}
    seller_claims = dataset.get("seller_claims") or {}

    # Bind tools to the active dataset
    set_context(dataset_id, {
        "required_columns": policy.required_columns or [],
        "column_definitions": column_definitions,
        "seller_claims": seller_claims,
    })

    required_str = ", ".join(policy.required_columns) if policy.required_columns else "(none)"
    definitions_str = (
        "\n".join(f"  {col}: {defn}" for col, defn in column_definitions.items())
        if column_definitions else "  (no definitions provided)"
    )
    claims_str = (
        "\n".join(f"  - {k}: {v}" for k, v in seller_claims.items())
        if seller_claims else "  (no claims provided)"
    )

    system_content = _SYSTEM_PROMPT.format(
        required_columns=required_str,
        column_definitions=definitions_str,
        seller_claims=claims_str,
    )

    det_note = (
        f"Deterministic metrics already computed:\n"
        f"  rows={metrics.row_count}, "
        f"  overall_null_rate={metrics.overall_null_rate:.1%}, "
        f"  duplicate_rate={metrics.duplicate_rate:.1%}, "
        f"  hard_constraints_pass={metrics.hard_constraints_pass}"
    )

    llm = get_llm(EVALUATE_MODEL).bind_tools(EVALUATE_TOOLS)
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=(
            f"Evaluate the dataset now.\n\n{det_note}\n\n"
            "Call get_schema_summary first, then any other tools you need, "
            "then output the final JSON."
        )),
    ]

    # Tool loop — LLM decides when to stop calling tools
    max_iterations = 10
    response = None
    for _ in range(max_iterations):
        response = llm.invoke(messages)
        messages.append(response)
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            break
        tool_node = ToolNode(EVALUATE_TOOLS)
        tool_results = tool_node.invoke({"messages": messages})
        messages.extend(tool_results["messages"])

    raw = response.content if response and isinstance(response.content, str) else ""

    # Nudge if LLM stopped without producing JSON
    if raw.strip() and not _looks_like_json(raw):
        messages.append(HumanMessage(content=(
            "Now output ONLY the final JSON object with schema_score, "
            "claim_veracity_score, schema_matching, claim_verification, and explanation."
        )))
        response = llm.invoke(messages)
        messages.append(response)
        raw = response.content if isinstance(response.content, str) else ""

    parsed = _parse_agent_output(raw, policy, seller_claims)
    return {"messages": messages, "eval_result": parsed}


# --- Graph builder ---

def _build_evaluate_graph():
    """Build and compile the single-node StateGraph for dataset evaluation."""
    graph = StateGraph(EvaluateState)
    graph.add_node("evaluate", evaluate_node)
    graph.set_entry_point("evaluate")
    graph.add_edge("evaluate", END)
    return graph.compile()


# --- Entry point ---

def run_agent(
    dataset_id: str,
    policy: BuyerPolicy,
    metrics: DatasetMetrics,
    component_scores: dict[str, float],
) -> dict[str, Any]:
    """
    Run the evaluate node for one dataset.

    Returns a dict with:
      schema_score, claim_veracity_score, schema_matching, claim_verification, explanation
    Falls back to safe defaults if the LLM output cannot be parsed.
    """
    graph = _build_evaluate_graph()

    initial_state: EvaluateState = {
        "messages": [],
        "dataset_id": dataset_id,
        "policy": policy,
        "metrics": metrics,
        "eval_result": {},
    }

    final_state = graph.invoke(initial_state, config={
        "recursion_limit": 50,
        "metadata": {"evaluate_prompt": EVALUATE_PROMPT_VERSION},
    })
    return final_state["eval_result"]


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _looks_like_json(text: str) -> bool:
    return bool(re.search(r'\{', text))


def _parse_agent_output(
    text: str,
    policy: BuyerPolicy,
    seller_claims: dict,
) -> dict[str, Any]:
    """Extract agent JSON from LLM response. Falls back to safe defaults."""
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()

    obj = None
    match = re.search(r'\{', text)
    if match:
        start = match.start()
        depth = 0
        in_str = False
        escape = False
        end = -1
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\" and in_str:
                escape = True
                continue
            if c == '"':
                in_str = not in_str
            if not in_str:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
        if end != -1:
            try:
                obj = json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError):
                obj = None

    if not obj:
        return _safe_defaults(policy, seller_claims)

    schema_score = float(obj.get("schema_score") or 0.5)
    schema_score = max(0.0, min(1.0, schema_score))

    claim_veracity_score = float(obj.get("claim_veracity_score") or 1.0)
    claim_veracity_score = max(0.0, min(1.0, claim_veracity_score))

    return {
        "schema_score": schema_score,
        "claim_veracity_score": claim_veracity_score,
        "schema_matching": obj.get("schema_matching") or {},
        "claim_verification": obj.get("claim_verification") or {},
        "explanation": str(obj.get("explanation") or ""),
    }


def _safe_defaults(policy: BuyerPolicy, seller_claims: dict) -> dict[str, Any]:
    """Return conservative defaults when agent output cannot be parsed."""
    return {
        "schema_score": 0.5,
        "claim_veracity_score": 1.0,
        "schema_matching": {col: None for col in policy.required_columns},
        "claim_verification": {k: "unverifiable" for k in seller_claims},
        "explanation": "Automated evaluation completed. Schema and claim verification results unavailable.",
    }
