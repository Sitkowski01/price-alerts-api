from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.security import require_api_key

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ApiKeyDep = Annotated[None, Depends(require_api_key)]
