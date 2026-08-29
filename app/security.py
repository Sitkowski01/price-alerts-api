import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Zapisy wymagają klucza. Odczyty zostawiamy otwarte — to nie są dane wrażliwe.

    Porównanie idzie przez `compare_digest`, a nie przez `!=`. Zwykłe porównanie
    napisów kończy się na pierwszym różniącym się znaku, więc czas odpowiedzi
    zdradza, ile początkowych znaków klucza się zgadza — to wystarcza, żeby
    odgadywać go znak po znaku zamiast zgadywać całość.
    """
    oczekiwany = get_settings().api_key

    # Porownujemy bajty, nie napisy: `compare_digest` na `str` dopuszcza wylacznie
    # znaki ASCII i przy innych rzuca TypeError — naglowek z polska litera
    # konczylby sie wtedy bledem 500 zamiast czystym 401.
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode("utf-8"), oczekiwany.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy lub brakujący nagłówek X-API-Key",
        )
