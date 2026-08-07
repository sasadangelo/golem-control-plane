# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Centralised configuration for the Golem Control Plane.

Settings are loaded from ``config.yaml`` (non-secret values) and ``.env``
(secrets). Import the ``settings`` singleton — never instantiate ``Settings``
directly elsewhere.

    from core.config import settings
"""

from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource

# Resolve paths relative to this file so they work regardless of the
# working directory uvicorn is launched from.
_HERE = Path(__file__).parent.parent  # src/golem-control-plane/
_CONFIG_YAML = str(_HERE / "config.yaml")
_ENV_FILE = str(_HERE / ".env")


class ControlPlaneConfig(BaseSettings):
    """HTTP server and provisioner settings."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    host: str = Field(default="0.0.0.0", description="Bind address for the uvicorn server.")  # nosec B104
    port: int = Field(default=9000, description="Bind port for the uvicorn server.")
    workers: int = Field(default=1, description="Number of uvicorn worker processes.")
    gc_interval: int = Field(default=60, description="TTL garbage-collector polling interval in seconds.")
    runner_image: str = Field(
        default="localhost/golem-runner:v1", description="Docker image used for agent runner pods."
    )


class LLMConfig(BaseSettings):
    """LLM provider settings (WatsonX)."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: str = Field(default="watsonx", description="LLM provider identifier.")
    protocol: str = Field(default="watsonx", description="LLM protocol identifier.")
    model: str = Field(default="openai/gpt-oss-120b", description="Model identifier used by agents.")
    project_id: str = Field(default="", description="WatsonX project ID.")
    url: str = Field(default="https://us-south.ml.cloud.ibm.com", description="WatsonX regional endpoint URL.")
    api_key: str = Field(
        default="",
        validation_alias="WATSONX_API_KEY",
        description="IBM Cloud API key. Secret — loaded from env var only.",
    )


class LogConfig(BaseSettings):
    """Logging settings."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    level: str = Field(default="INFO", description="Minimum log level.")
    console: bool = Field(default=True, description="Whether to log to stdout.")
    file: str = Field(default="logs/golem-control-plane.log", description="Path to the log file.")
    rotation: str = Field(default="10 MB", description="Log file rotation policy.")
    retention: str = Field(default="7 days", description="Log file retention policy.")
    compression: str = Field(default="zip", description="Compression format for rotated files.")


class Settings(BaseSettings):
    """Root settings — single source of truth for the entire application."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        yaml_file=_CONFIG_YAML,
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    control_plane: ControlPlaneConfig = Field(default_factory=ControlPlaneConfig, alias="control-plane")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, env_settings, dotenv_settings, YamlConfigSettingsSource(settings_cls)


settings: Settings = Settings()
