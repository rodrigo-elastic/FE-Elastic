"""
filename: config.py
description: Settings loaded from environment via pydantic-settings.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field("development", alias="APP_ENV")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")

    # Default model for every agent. Cheapest tier by default; override per agent below.
    model_default: str = Field("claude-haiku-4-5", alias="MODEL_DEFAULT")
    model_pre_meeting: str = Field("", alias="MODEL_PRE_MEETING")
    model_post_meeting: str = Field("", alias="MODEL_POST_MEETING")
    model_live_meeting: str = Field("", alias="MODEL_LIVE_MEETING")

    elasticsearch_url: str = Field("http://localhost:9200", alias="ELASTICSEARCH_URL")
    elasticsearch_username: str = Field("elastic", alias="ELASTICSEARCH_USERNAME")
    elasticsearch_password: str = Field("", alias="ELASTICSEARCH_PASSWORD")
    elasticsearch_api_key: str = Field("", alias="ELASTICSEARCH_API_KEY")
    kibana_url: str = Field("http://localhost:5601", alias="KIBANA_URL")
    kibana_api_key: str = Field("", alias="KIBANA_API_KEY")

    runtime_dir: Path = Field(Path("./runtime"), alias="RUNTIME_DIR")
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"])

    def model_for(self, agent: str) -> str:
        """Resolve the model id for a given agent slug, falling back to MODEL_DEFAULT."""
        override = {
            "pre_meeting": self.model_pre_meeting,
            "post_meeting": self.model_post_meeting,
            "live_meeting": self.model_live_meeting,
        }.get(agent, "")
        return override or self.model_default


settings = Settings()
settings.runtime_dir.mkdir(parents=True, exist_ok=True)
