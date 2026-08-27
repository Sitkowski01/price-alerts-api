import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Logi w JSON — w Kubernetesie i tak zbiera je agent, a tekst trzeba potem parsować."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for pole in ("method", "path", "status_code", "duration_ms", "request_id"):
            if hasattr(record, pole):
                payload[pole] = getattr(record, pole)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Uvicorn ma wlasne handlery — bez tego kazda linia bylaby podwojona.
    for nazwa in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(nazwa)
        logger.handlers.clear()
        logger.propagate = True
