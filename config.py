from __future__ import annotations
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # NearAI API — all models served via NearAI confidential compute
    nearai_api_key: str = ""
    nearai_base_url: str = "https://cloud-api.near.ai/v1"
    default_model: str = "deepseek-ai/DeepSeek-V3.1"

    # Embedding (unchanged)
    embedding_model: str = "all-MiniLM-L6-v2"

    # Supabase auth (optional — if unset, /auth/* endpoints return 503 and /register is the fallback)
    supabase_url: str = ""
    supabase_anon_key: str = ""

    model_config = {"env_prefix": "CONCLAVE_", "env_file": ".env", "extra": "ignore"}


settings = Settings()


def get_llm(model: str | None = None):
    """Return the configured LangChain chat model via NearAI.

    model: specific model ID to use. Falls back to settings.default_model if None.
    Skills declare their own per-node models in their own config.py.
    """
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model or settings.default_model,
        api_key=settings.nearai_api_key,
        base_url=settings.nearai_base_url,
    )
