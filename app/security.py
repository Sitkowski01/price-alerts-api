from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Zapisy wymagają klucza. Odczyty zostawiamy otwarte — to nie są dane wrażliwe."""
    if x_api_key != get_settings().api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy lub brakujący nagłówek X-API-Key",
        )
