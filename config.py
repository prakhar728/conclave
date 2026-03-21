from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    llm_provider: Literal["openai", "anthropic", "google", "nearai"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    google_api_key: str = ""
    nearai_api_key: str = ""
    nearai_model: str = "deepseek-ai/DeepSeek-V3.1"
    embedding_model: str = "all-MiniLM-L6-v2"

    # Supabase auth (optional — if unset, /auth/* endpoints return 503 and /register is the fallback)
    supabase_url: str = ""
    supabase_anon_key: str = ""

    model_config = {"env_prefix": "CONCLAVE_", "env_file": ".env", "extra": "ignore"}


settings = Settings()


def get_llm():
    """Return the configured LangChain chat model."""
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)
    elif settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-sonnet-4-6", api_key=settings.anthropic_api_key)
    elif settings.llm_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=settings.google_api_key)
    elif settings.llm_provider == "nearai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.nearai_model,
            api_key=settings.nearai_api_key,
            base_url="https://cloud-api.near.ai/v1",
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
