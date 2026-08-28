"""Configuração da aplicação.

Toda a configuração entra por variável de ambiente — nada de valor sensível no
código. Ver `.env.example` na raiz do repositório.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Aplicação
    app_name: str = "FlyHub System API"
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    # NoDecode desliga o json.loads que a fonte de ambiente aplica a campos de
    # tipo complexo. Sem ele, `CORS_ORIGINS=a,b` estoura antes do validator
    # abaixo ser chamado — o parse acontece na leitura, não na validação.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # Banco
    database_url: str = "postgresql+asyncpg://flyhub:flyhub@db:5432/flyhub"

    # FlightHub / MediaMTX
    flyhub_rtmp_host: str = "mediamtx"
    flyhub_rtmp_port: int = 1935
    flyhub_stream_path: str = "live/m4td"
    mediamtx_api_url: str = "http://mediamtx:9997"
    mediamtx_rtsp_url: str = "rtsp://mediamtx:8554"
    # Endereço fixo que o operador cola no FlightHub. O M4TD deixou de depender
    # do túnel: com PUBLIC_HOST definido o endereço não muda entre reinícios.
    # Vazio faz o endereço ser montado com o host do próprio MediaMTX.
    flyhub_public_host: str = ""
    tunnel_enabled: bool = False
    tunnel_public_host: str = ""

    # Fonte de telemetria de voo
    # `fake` é o padrão de propósito: quem clona o repositório vê a aplicação
    # inteira funcionando — drone, decolagem, mapa — sem hardware nenhum.
    # `real` consulta o MediaMTX de verdade e consome o RTSP; a posição GPS
    # continua ausente até o FlightHub Sync entrar, e é isso que `mqtt` reserva.
    flight_source: Literal["fake", "real", "mqtt"] = "fake"
    fake_flight_interval: float = 1.0
    fake_flight_speed_ms: float = 6.0
    # Terminal Marítimo de Ponta Ubu, Anchieta/ES.
    fake_flight_center_lat: float = -20.78667
    fake_flight_center_lon: float = -40.57333

    # Vídeo e inferência
    # Pesos ausentes não são erro: é o estado inicial do projeto, e o detector
    # responde em passthrough. Ver `integrations/vision/detector.py`.
    model_weights: Path | None = None
    model_conf: float = 0.25
    jpeg_quality: int = 80

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

    @field_validator("model_weights", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: str | Path | None) -> str | Path | None:
        """`MODEL_WEIGHTS=` no .env significa "use o padrão", não `Path(".")`."""
        return value or None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str | list[str]) -> list[str]:
        """Aceita `a,b` e `["a","b"]`.

        A vírgula é o formato do .env.example, por ser legível. O JSON é aceito
        porque é o que pydantic-settings faria por padrão, e porque plataformas
        de deploy costumam gerar variáveis nesse formato.
        """
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def roboflow_configured(self) -> bool:
        return bool(self.roboflow_api_key and self.roboflow_workspace and self.roboflow_project)

    @property
    def mediamtx_host(self) -> str:
        """Host de `MEDIAMTX_API_URL`. É onde o broker realmente está."""
        return urlparse(self.mediamtx_api_url).hostname or self.flyhub_rtmp_host

    @property
    def rtmp_publish_url(self) -> str:
        """Endereço que o operador cola no FlightHub 2 para publicar o stream.

        Ordem de precedência: o host público fixo, depois o túnel (que muda a
        cada reinício), depois o host do próprio broker. O primeiro é o modo
        que o M4TD passou a usar — endereço estável entre reinícios.
        """
        host = self.flyhub_public_host or self.tunnel_public_host or self.mediamtx_host
        if ":" not in host:
            host = f"{host}:{self.flyhub_rtmp_port}"
        return f"rtmp://{host}/{self.flyhub_stream_path}"

    @property
    def rtsp_url(self) -> str:
        """Endereço que o leitor de quadros consome."""
        return f"{self.mediamtx_rtsp_url.rstrip('/')}/{self.flyhub_stream_path}"

    @property
    def weights_path(self) -> Path:
        """Arquivo de pesos do detector. Pode não existir — e isso é normal."""
        return self.model_weights or (self.models_dir / "best.pt")

    @property
    def video_enabled(self) -> bool:
        """Só a fonte real consome RTSP; `fake` não tem broker para ler."""
        return self.flight_source != "fake"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
