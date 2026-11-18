"""Configuración: única puerta de entrada a las variables de `.env`."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    demo_mode: bool = True
    dry_run: bool = True

    anthropic_api_key: str = ""
    classifier_model: str = "claude-haiku-5-5"
    confidence_threshold: float = 0.80
    # Si las dos opciones de la IA están a menos de este margen, va al supervisor.
    confidence_gap: float = 0.15

    siigo_username: str = ""
    siigo_access_key: str = ""
    siigo_partner_id: str = ""

    # Modo demo: 1.0 = tiempos realistas, 0 = instantáneo (tests).
    demo_delay_factor: float = 1.0
    # Modo demo: simula que la DIAN pide verificación humana unos segundos.
    demo_simular_pausa: bool = False

    database_url: str = f"sqlite:///{ROOT / 'data' / 'app.db'}"

    def __repr__(self) -> str:  # nunca mostrar llaves
        return f"Settings(demo_mode={self.demo_mode}, dry_run={self.dry_run})"

    __str__ = __repr__


@lru_cache
def get_settings() -> Settings:
    return Settings()
