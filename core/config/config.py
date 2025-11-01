import os
from functools import lru_cache
from typing import List
import logging

from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    bot_token: str = Field(..., description="Telegram Bot Token")
    admin_ids: List[int] = Field(default_factory=list, description="Bot Admins (numeric IDs)")

    # LLM Plugin Gemini API Key
    gemini_api_key: str = Field("", description="Gemini API Key for LLM plugin integration")

    # admin-configurable settings (persisted via AdminSettingsManager)
    language: str = Field("en", description="Default language")
    timezone: str = Field("Africa/Cairo", description="Default timezone")
    notifications: bool = Field(True, description="Enable notifications for scheduled jobs")
    default_target: str = Field("all", description="Default schedule target: individuals|groups|all")
    time_format: str = Field("24h", description="Time format: 12h or 24h")
    log_level: str = Field("info", description="Logging level")

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


def clear_settings_cache() -> None:
    get_settings.cache_clear()


@lru_cache()
def get_settings() -> Settings:
    logger.info("Loading application configuration settings.")
    return Settings()
