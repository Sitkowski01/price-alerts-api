from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Konfiguracja wyłącznie ze zmiennych środowiskowych — nic nie jest zaszyte w kodzie."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    api_key: str

    app_env: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"

    # Górny limit stronicowania. Bez niego jeden klient potrafi poprosić o całą tabelę.
    max_page_size: int = 200

    # Skąd wolno wołać API z przeglądarki. Domyślnie adresy deweloperskie Vite —
    # bez tego klient webowy dostaje od przeglądarki odmowę jeszcze przed zapytaniem.
    # Na produkcji podaje się konkretną domenę, nigdy "*".
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _rozdziel(cls, value: object) -> object:
        # Zmienna środowiskowa przychodzi jako tekst rozdzielony przecinkami.
        if isinstance(value, str):
            return [fragment.strip() for fragment in value.split(",") if fragment.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
