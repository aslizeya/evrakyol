import logging
import sys
import threading
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.admin import router as admin_router
from app.api_v1 import get_retriever
from app.api_v1 import router as v1_router
from app.config import get_settings
from app.db import get_session

logger = logging.getLogger(__name__)

# Windows konsolunda Türkçe karakterli kayıtlar bozulmasın
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().retriever_backend == "memory":
        # Veritabanısız denemede kaynaklar açılışta arka planda indirilir.
        retriever = get_retriever()
        threading.Thread(target=retriever.warm_up, name="kaynak-onbellek", daemon=True).start()
    yield


app = FastAPI(title="Evrakyol API", version="0.1.0", lifespan=lifespan)
app.include_router(admin_router)
app.include_router(v1_router)


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
