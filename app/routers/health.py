from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.deps import SessionDep

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    """Czy proces żyje. Celowo nie dotyka bazy — inaczej chwilowa awaria
    Postgresa kazałaby Kubernetesowi ubić skądinąd zdrowy pod."""
    return {"status": "ok"}


@router.get("/readyz")
async def readiness(response: Response, session: SessionDep) -> dict:
    """Czy pod może przyjmować ruch. Tu baza jest sprawdzana naprawdę."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - powod chcemy zobaczyc w odpowiedzi
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "database": "unreachable", "detail": str(exc)[:200]}

    return {"status": "ok", "database": "reachable"}
