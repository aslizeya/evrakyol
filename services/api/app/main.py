import logging
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session

logger = logging.getLogger(__name__)

app = FastAPI(title="Evrakyol API", version="0.1.0")


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]


@app.get("/health", response_model=HealthResponse)
def health(response: Response, session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        # Bağlantı adresi gizli bilgi içerebileceği için hata ayrıntısı yanıta konmaz.
        logger.exception("Veritabanı sağlık kontrolü başarısız")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", database="unavailable")
    return HealthResponse(status="ok", database="ok")
