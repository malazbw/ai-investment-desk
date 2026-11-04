"""
Application configuration
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Database - check for env var first, then .env, then default
    # Use SQLite for development if DATABASE_URL not set
    database_url: str = "sqlite:///./ai_investment_desk.db"

    # Broker credentials (will be fetched from .env)
    scalable_capital_api_key: str = ""
    scalable_capital_api_secret: str = ""
    binance_api_key: str = ""
    binance_api_secret: str = ""

    # FRED API
    fred_api_key: str = ""

    # SEC EDGAR submissions API (identify requests with a contact email)
    sec_user_agent: str = ""

    # NewsAPI
    newsapi_key: str = ""

    # eToro market data
    etoro_api_key: str = ""
    etoro_user_key: str = ""

    # Claude API (Anthropic) - optional, for paid model
    claude_api_key: str = ""
    claude_model: str = "claude-opus-4-1"

    # Gemini API (Google AI Studio)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    # LLM provider selection
    llm_provider: str = "ollama"
    ollama_api_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"  # or "neural-chat", "llama2", etc

    # LLM (future)
    openai_api_key: str = ""

    # App settings
    debug: bool = True
    log_level: str = "INFO"
    app_name: str = "AI Investment Desk"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings():
    # Allow DATABASE_URL from environment to override .env
    if "DATABASE_URL" in os.environ:
        return Settings(database_url=os.environ["DATABASE_URL"])
    return Settings()


settings = get_settings()
