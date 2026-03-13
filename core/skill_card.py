from __future__ import annotations
"""
SkillCard — the self-declaration contract every skill must provide.

IMPORTANT — Input Sanitization Invariant
-----------------------------------------
Today, raw submission text never reaches the LLM. Agents see only tool
outputs (novelty_score, percentile, cluster). Prompt injection via
submission content is impossible under this constraint.

If you add a tool that exposes ANY raw text to the LLM (e.g. a summarizer,
keyword extractor, or any function that reads from _submissions), you MUST
sanitize inputs before that text enters the prompt. Strip or redact
adversarial content before passing it as tool output or system context.
Failure to do so opens a direct prompt injection vector.
"""
from dataclasses import dataclass, field
from typing import Callable, Any, Type

from pydantic import BaseModel


@dataclass
class SkillCard:
    name: str
    description: str
    run: Callable                    # the run_skill() entry point
    input_model: Type[BaseModel]     # Pydantic model for this skill's inputs
    output_keys: set                 # allowed output keys (mirrors ALLOWED_OUTPUT_KEYS)
    config: dict = field(default_factory=dict)   # skill-specific config params
    version: str = "0.1.0"

    def metadata(self) -> dict:
        """JSON-serializable card metadata for the /skills endpoint."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "input_schema": self.input_model.model_json_schema(),
            "output_keys": sorted(self.output_keys),
            "config": self.config,
        }
