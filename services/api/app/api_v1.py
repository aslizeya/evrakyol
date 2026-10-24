"""Web uygulamasının çağırdığı soru anlama ve yol haritası uç noktaları."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.db import get_sessionmaker
from app.embedding import get_embedder
from app.llm import LLMError, LLMProvider, get_llm
from app.process_types import get_process_type, get_process_types
from app.rag.retrieval import HybridRetriever, Retriever
from app.rag.roadmap import RoadmapGenerationError, RoadmapService
from app.rag.schema import Roadmap
from app.rag.understanding import UnderstandingError, understand, valid_answers
from app.security import require_internal_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["v1"], dependencies=[Depends(require_internal_token)])

TEXT_LIMIT = 2000
Answers = Annotated[dict[str, Annotated[str, Field(max_length=200)]], Field(max_length=10)]


def get_retriever() -> Retriever:
    return HybridRetriever(get_sessionmaker(), get_embedder())


LlmDep = Annotated[LLMProvider, Depends(get_llm)]
RetrieverDep = Annotated[Retriever, Depends(get_retriever)]


def _llm_unavailable(exc: LLMError) -> HTTPException:
    logger.warning("LLM çağrısı başarısız: %s", exc.reason)
    if exc.reason == "budget_exceeded":
        detail = "Günlük kullanım sınırına ulaşıldı. Lütfen daha sonra tekrar deneyin."
    else:
        detail = "Yanıt şu anda oluşturulamıyor. Lütfen biraz sonra tekrar deneyin."
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail)


# --- soru anlama ---


class UnderstandRequest(BaseModel):
    text: str = Field(min_length=3, max_length=TEXT_LIMIT)
    process_code: str | None = None
    answers: Answers = {}


class Question(BaseModel):
    key: str
    question: str
    options: list[str]


class UnderstandResponse(BaseModel):
    status: Literal["out_of_scope", "needs_clarification", "ready"]
    masked_text: str
    process_code: str | None = None
    process_name: str | None = None
    answers: dict[str, str] = {}
    questions: list[Question] = []
    message: str | None = None


OUT_OF_SCOPE_MESSAGE = (
    "Bu işlem şu an desteklenen işlemler arasında değil. Desteklenen işlemler: {names}. "
    "Diğer işlemler için ilgili kurumun resmi sitesine veya e-Devlet'e başvurabilirsiniz."
)


@router.post("/understand", response_model=UnderstandResponse)
def understand_endpoint(body: UnderstandRequest, llm: LlmDep) -> UnderstandResponse:
    process_types = list(get_process_types())
    try:
        result = understand(
            body.text,
            llm=llm,
            process_types=process_types,
            process_code=body.process_code,
            answers=body.answers,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except LLMError as exc:
        raise _llm_unavailable(exc) from exc
    except UnderstandingError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "İsteğiniz anlaşılamadı. Lütfen farklı ifade edin."
        ) from exc

    if result.status == "out_of_scope":
        names = ", ".join(p.name for p in process_types)
        return UnderstandResponse(
            status="out_of_scope",
            masked_text=result.masked_text,
            message=OUT_OF_SCOPE_MESSAGE.format(names=names),
        )
    if result.process is None:  # "out_of_scope" dışındaki durumlarda işlem her zaman bellidir
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Beklenmeyen durum")
    return UnderstandResponse(
        status=result.status,
        masked_text=result.masked_text,
        process_code=result.process.code,
        process_name=result.process.name,
        answers=result.answers,
        questions=[Question(**q.model_dump()) for q in result.questions],
    )


# --- yol haritası ---


class RoadmapRequest(BaseModel):
    text: str = Field(min_length=3, max_length=TEXT_LIMIT)
    process_code: str
    answers: Answers = {}


class RoadmapMeta(BaseModel):
    dropped_steps: int
    dropped_warnings: int
    model: str | None
    source_ids: list[int]


class RoadmapResponse(BaseModel):
    status: Literal["ok", "no_sources"]
    masked_text: str
    roadmap: Roadmap | None = None
    message: str | None = None
    referral: str | None = None
    meta: RoadmapMeta


NO_SOURCES_MESSAGE = (
    "Bu işlem için resmi kaynaklarda yeterli bilgi bulunamadı. Yanlış yönlendirmemek için "
    "yol haritası oluşturulmadı. Lütfen {referral} ile iletişime geçin."
)


@router.post("/roadmap", response_model=RoadmapResponse)
def roadmap_endpoint(body: RoadmapRequest, llm: LlmDep, retriever: RetrieverDep) -> RoadmapResponse:
    process = get_process_type(body.process_code)
    if process is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Bilinmeyen işlem kodu")
    try:
        outcome = RoadmapService(retriever, llm).build(
            body.text, process, valid_answers(process, body.answers)
        )
    except LLMError as exc:
        raise _llm_unavailable(exc) from exc
    except RoadmapGenerationError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Yanıt doğrulanamadı. Yanlış bilgi vermemek için yol haritası gösterilmiyor; "
            "lütfen tekrar deneyin.",
        ) from exc

    meta = RoadmapMeta(
        dropped_steps=outcome.dropped_steps,
        dropped_warnings=outcome.dropped_warnings,
        model=outcome.model,
        source_ids=outcome.source_ids,
    )
    if outcome.status == "no_sources":
        return RoadmapResponse(
            status="no_sources",
            masked_text=outcome.masked_text,
            message=NO_SOURCES_MESSAGE.format(referral=outcome.referral),
            referral=outcome.referral,
            meta=meta,
        )
    return RoadmapResponse(
        status="ok", masked_text=outcome.masked_text, roadmap=outcome.roadmap, meta=meta
    )
