from functools import lru_cache
from typing import Literal

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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
