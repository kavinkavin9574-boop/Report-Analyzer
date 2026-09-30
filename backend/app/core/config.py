"""
Central application configuration.

Everything is read from environment variables (see .env.example at the repo
root). Nothing here should ever contain a hard-coded secret or API key.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore", protected_namespaces=("settings_",)
    )

    # --- AI provider ---
    ai_provider: str = "openai"
    openai_default_model: str = "gpt-4o"
    openai_fast_model: str = "gpt-4o-mini"
    openai_reasoning_model: str = "gpt-4o"

    # --- Database ---
    database_url: str = "postgresql+psycopg2://docai:docai@localhost:5432/docai"

    # --- Auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # --- Storage ---
    storage_path: str = "./storage"
    max_file_size: int = 25 * 1024 * 1024

    # --- OCR (PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR) ---
    ocr_enabled: bool = True
    paddleocr_language: str = "en"
    paddleocr_device: str = "cpu"      # use gpu:0 with a compatible PaddlePaddle GPU install



@lru_cache
def get_settings() -> Settings:
    return Settings()
