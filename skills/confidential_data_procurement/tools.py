"""
Aggregate-only data tools for the confidential_data_procurement evaluate node.

Security:
  - Tools NEVER return raw rows or individual cell values.
  - All output passes through validate_tool_output() before leaving the tool.
  - The LLM sees aggregate statistics only — it cannot reconstruct the dataset.

Tools:
  1. get_schema_summary()              — column names, dtypes, null rates, row count
  2. get_column_stats(column_name)     — numeric: min/max/mean/std; categorical: top-5 counts
  3. get_value_distribution(col, n)    — top-N value counts + distinct count

What to edit here:
  - Add a new tool: define @tool function, add to EVALUATE_TOOLS.
  - Change cardinality / size limits: update constants in guardrails.py.
"""
from __future__ import annotations

from langchain_core.tools import tool

from skills.confidential_data_procurement.guardrails import validate_tool_output

# ---------------------------------------------------------------------------
# Module-level context — set by set_context() in __init__.py before agent runs
# ---------------------------------------------------------------------------

_dataset_id: str = ""
_policy_context: dict = {}   # required_columns, column_definitions, seller_claims


def set_context(dataset_id: str, policy_context: dict) -> None:
    """Bind the active dataset and policy context for this evaluation run.
    Called by run_skill() before run_agent().
    """
    global _dataset_id, _policy_context
    _dataset_id = dataset_id
    _policy_context = policy_context


def _get_df():
    from skills.confidential_data_procurement.ingest import get_dataset
    return get_dataset(_dataset_id)["df"]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def get_schema_summary() -> str:
    """
    Get a summary of the dataset schema.

    Returns: column names, data types, null rate per column, row count, column count.
    Call this first to understand what columns are present and their data quality.
    """
    df = _get_df()
    lines = [f"rows: {len(df)}", f"columns ({len(df.columns)}):"]
    for col in df.columns:
        dtype = str(df[col].dtype)
        null_rate = float(df[col].isna().mean())
        lines.append(f"  {col}: dtype={dtype}, null_rate={null_rate:.1%}")
    return validate_tool_output("\n".join(lines))


@tool
def get_column_stats(column_name: str) -> str:
    """
    Get aggregate statistics for a single column.

    Numeric columns: min, max, mean, median, std, non-null count.
    Categorical columns: total distinct values, top-5 most frequent values with counts.
    Returns an error if the column does not exist.
    """
    df = _get_df()
    if column_name not in df.columns:
        available = ", ".join(list(df.columns)[:10])
        return f"Column '{column_name}' not found. Available columns: {available}"

    col = df[column_name].dropna()
    if len(col) == 0:
        return validate_tool_output(f"column: {column_name}\nAll values are null.")

    if col.dtype.kind in ("i", "f", "u"):
        output = (
            f"column: {column_name} (numeric)\n"
            f"count: {len(col)}\n"
            f"min: {col.min():.4g}\n"
            f"max: {col.max():.4g}\n"
            f"mean: {col.mean():.4g}\n"
            f"median: {col.median():.4g}\n"
            f"std: {col.std():.4g}"
        )
    else:
        top = col.value_counts().head(5)
        top_lines = "\n".join(f"  {v}: {c}" for v, c in top.items())
        output = (
            f"column: {column_name} (categorical)\n"
            f"count: {len(col)}\n"
            f"distinct: {col.nunique()}\n"
            f"top-5:\n{top_lines}"
        )

    return validate_tool_output(output)


@tool
def get_value_distribution(column_name: str, top_n: int = 10) -> str:
    """
    Get the top-N most frequent values for a column with their counts and percentages.

    top_n is capped at 20. Use this to assess label distribution (e.g. fraud rate),
    category balance, or unusual value concentration. Returns total distinct count too.
    """
    df = _get_df()
    if column_name not in df.columns:
        return f"Column '{column_name}' not found."

    top_n = min(max(top_n, 1), 20)
    col = df[column_name].dropna()
    total = len(col)
    total_distinct = col.nunique()
    top = col.value_counts().head(top_n)

    lines = [
        f"column: {column_name}",
        f"total non-null: {total}",
        f"total distinct: {total_distinct}",
        f"top-{top_n}:",
    ]
    for val, count in top.items():
        pct = count / total * 100 if total > 0 else 0
        lines.append(f"  {val}: {count} ({pct:.1f}%)")

    return validate_tool_output("\n".join(lines))


# Tool group — bound to evaluate_node in agent.py
EVALUATE_TOOLS = [get_schema_summary, get_column_stats, get_value_distribution]
