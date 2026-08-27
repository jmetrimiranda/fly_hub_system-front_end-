"""Configuração da aplicação.

Toda a configuração entra por variável de ambiente — nada de valor sensível no
código. Ver `.env.example` na raiz do repositório.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Aplicação
    app_name: str = "FlyHub System API"
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Banco
    database_url: str = "postgresql+asyncpg://flyhub:flyhub@db:5432/flyhub"

    # FlightHub / MediaMTX
    flyhub_rtmp_host: str = "mediamtx"
    flyhub_rtmp_port: int = 1935
    flyhub_stream_path: str = "live/m4td"
    mediamtx_api_url: str = "http://mediamtx:9997"
    mediamtx_rtsp_url: str = "rtsp://mediamtx:8554"
    tunnel_enabled: bool = False
    tunnel_public_host: str = ""

    # Armazenamento
    data_root: Path = Path("/data")
    datasets_dir: Path = Path("/data/datasets")
    models_dir: Path = Path("/data/models")

    # Split temporal
    split_train_ratio: float = 0.70
    split_valid_ratio: float = 0.15
    split_test_ratio: float = 0.15
    split_embargo_seconds: int = 5

    # Roboflow
    roboflow_api_key: str = ""
    roboflow_workspace: str = ""
    roboflow_project: str = ""
    roboflow_api_url: str = "https://api.roboflow.com"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def roboflow_configured(self) -> bool:
        return bool(self.roboflow_api_key and self.roboflow_workspace and self.roboflow_project)

    @property
    def rtmp_publish_url(self) -> str:
        """Endereço que o operador cola no FlightHub 2 para publicar o stream."""
        host = self.tunnel_public_host or f"{self.flyhub_rtmp_host}:{self.flyhub_rtmp_port}"
        return f"rtmp://{host}/{self.flyhub_stream_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
