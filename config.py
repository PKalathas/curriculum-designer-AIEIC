"""
Curriculum Designer configuration.

All settings are read from environment variables (or a .env file).
Copy .env.example -> .env to get started.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Service ───────────────────────────────────────────────────────────────
    service_port: int = 8003
    service_name: str = "curriculum-designer"
    version: str = "0.1.0"

    # ── Azure OpenAI (Stage B) ────────────────────────────────────────────────
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment_name: str = "gpt-4o"   # env var: AZURE_OPENAI_DEPLOYMENT_NAME
    azure_openai_api_version: str = "2024-08-01-preview"

    # ── LLM backend ──────────────────────────────────────────────────────────
    # "azure" = Azure OpenAI calls
    # "openai_compatible" = OpenAI-compatible chat completions APIs
    # "mock" = stub data for dev/test
    llm_backend: str = "azure"

    # ── OpenAI-compatible APIs ────────────────────────────────────────────────
    # Works with OpenAI, DeepSeek, OpenRouter, and similar providers.
    # Examples:
    #   OpenAI:  LLM_BASE_URL=, LLM_MODEL=gpt-5-nano
    #   DeepSeek: LLM_BASE_URL=https://api.deepseek.com, LLM_MODEL=deepseek-v4-flash
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-5-nano"

    # ── Storage ───────────────────────────────────────────────────────────────
    # "postgres" is the integrated runtime backend. "memory" remains for tests.
    storage_backend: str = "postgres"
    database_url: str = ""


settings = Settings()
