"""
Agentic ingestion node for the hackathon_novelty skill.

Runs BEFORE the deterministic layer. Normalizes submission text from various
formats (plain text, markdown, docx) and conditionally summarizes long content.

What makes it agentic:
- Short plain text → get_raw_text → done (1 tool call)
- Markdown → parse_markdown → check length → maybe summarize_text (1-2 tool calls)
- Docx → extract_docx → check length → maybe summarize_text (1-2 tool calls)
- Long text → get_raw_text → summarize_text (2 tool calls)
- Different submissions take different tool-call paths in the same run.

The LLM decides which tools to call based on each submission's format and length.
"""
from __future__ import annotations
import json
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import ToolNode

from config import get_llm
from skills.hackathon_novelty.tools import INGEST_TOOLS, set_context as _set_tool_context, _submissions
from skills.hackathon_novelty.config import INGEST_MODEL


INGEST_PROMPT_VERSION = "v1"

INGEST_SYSTEM_PROMPT = """You are an ingestion agent preparing hackathon submissions for evaluation.

For each submission, you must normalize the idea into clean, comparable text.

PROCESS (apply for each submission_id):
1. Check the submission's format:
   - If idea_file_type is "docx": call extract_docx
   - If idea_file_type is "markdown": call parse_markdown
   - If idea_file_type is null/text: call get_raw_text
2. Review the extracted text length (word_count in tool response):
   - If the text exceeds 300 words: call summarize_text to condense it
   - If under 300 words: use the extracted text as-is
3. Record the final normalized text for that submission

After processing ALL submissions, output a JSON object mapping submission_id to normalized text:
{{"sub_001": "normalized text...", "sub_002": "normalized text..."}}
"""


def run_ingest(submissions) -> dict[str, str]:
    """Run the ingestion node to normalize text from various formats.

    Args:
        submissions: list of HackathonSubmission objects

    Returns:
        dict mapping submission_id to normalized text string.
        On failure, returns empty dict (caller uses raw idea_text as fallback).
    """
    if not submissions:
        return {}

    # Set up tool context so ingestion tools can access submissions
    subs_map = {s.submission_id: s for s in submissions}
    # Directly set module-level _submissions in tools.py
    import skills.hackathon_novelty.tools as tools_mod
    tools_mod._submissions = subs_map

    llm = get_llm(INGEST_MODEL).bind_tools(INGEST_TOOLS)

    # Build human message with submission metadata
    lines = []
    for s in submissions:
        file_type = s.idea_file_type or "text"
        word_count = len(s.idea_text.split())
        lines.append(f"  {s.submission_id}: format={file_type}, idea_word_count={word_count}")
    submissions_str = "\n".join(lines)

    messages = [
        SystemMessage(content=INGEST_SYSTEM_PROMPT),
        HumanMessage(content=f"Process these submissions:\n{submissions_str}"),
    ]

    # Tool loop — same pattern as triage_node
    max_iterations = 30  # ~2 tool calls per submission on average
    iteration = 0
    response = None
    while iteration < max_iterations:
        response = llm.invoke(messages)
        messages.append(response)
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            break
        tool_node = ToolNode(INGEST_TOOLS)
        tool_results = tool_node.invoke({"messages": messages})
        messages.extend(tool_results["messages"])
        iteration += 1

    if response is None:
        return {}

    # If model stopped without outputting the JSON map, nudge it
    raw = response.content if isinstance(response.content, str) else str(response.content)
    if not raw.strip() and iteration > 0:
        messages.append(HumanMessage(content="Now output the final JSON mapping of submission_id to normalized text."))
        response = llm.invoke(messages)
        raw = response.content if isinstance(response.content, str) else str(response.content)

    # Parse the JSON output
    return _parse_ingest_output(raw, submissions)


def _parse_ingest_output(text: str, submissions) -> dict[str, str]:
    """Extract normalized text mapping from LLM response.
    Returns dict of {submission_id: normalized_text}. Missing IDs are omitted
    (caller falls back to raw idea_text).
    """
    result = {}
    try:
        # Find the JSON object in the response
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
                if c == '\\' and in_str:
                    escape = True
                    continue
                if c == '"':
                    in_str = not in_str
                if not in_str:
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
            if end != -1:
                obj = json.loads(text[start:end])
                valid_ids = {s.submission_id for s in submissions}
                for sid, normalized in obj.items():
                    if sid in valid_ids and isinstance(normalized, str) and normalized.strip():
                        result[sid] = normalized.strip()
    except (json.JSONDecodeError, TypeError):
        pass

    return result
