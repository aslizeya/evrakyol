"""Sorularla ilerleyen rehberin uç noktası. Durumsuzdur: istemci o ana kadarki cevapları
gönderir, sunucu sıradaki soruyu ya da yol haritasını döndürür."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.ingest.sources_config import get_sources_config
from app.process_types import get_process_type
from app.rag.schema import Roadmap
from app.rehber import (
    build_roadmap,
    effective_answers,
    get_guides,
    get_verification,
    next_question,
    remaining_questions,
)
from app.security import require_internal_token

router = APIRouter(
    prefix="/v1/rehber", tags=["rehber"], dependencies=[Depends(require_internal_token)]
)

Answers = Annotated[dict[str, Annotated[str, Field(max_length=200)]], Field(max_length=10)]


class GuideSummary(BaseModel):
    islem: str
    ad: str
    aciklama: str


class GuideRequest(BaseModel):
    islem: str = Field(max_length=64)
    cevaplar: Answers = {}


class Question(BaseModel):
    anahtar: str
    metin: str
    secenekler: list[str]


class Progress(BaseModel):
    cevaplanan: int
    toplam: int


class GuideResponse(BaseModel):
    durum: Literal["soru", "tamam", "kaynak_yok"]
    cevaplar: dict[str, str]  # geçerli sayılan cevaplar (istemci kendi durumunu bununla eşitler)
    soru: Question | None = None
    ilerleme: Progress | None = None
    yol_haritasi: Roadmap | None = None
    mesaj: str | None = None


@router.get("", response_model=list[GuideSummary])
def list_guides() -> list[GuideSummary]:
    result = []
    for code in get_guides():
        process = get_process_type(code)
        if process:
            result.append(GuideSummary(islem=code, ad=process.name, aciklama=process.description))
    return result


@router.post("", response_model=GuideResponse)
def guide_step(body: GuideRequest) -> GuideResponse:
    guide = get_guides().get(body.islem)
    process = get_process_type(body.islem)
    if guide is None or process is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bu işlem için rehber bulunmuyor")

    answers = effective_answers(guide, process, body.cevaplar)
    question = next_question(guide, process, answers)
    if question is not None:
        return GuideResponse(
            durum="soru",
            cevaplar=answers,
            soru=Question(
                anahtar=question.key, metin=question.question, secenekler=question.options
            ),
            ilerleme=Progress(
                cevaplanan=len(answers), toplam=len(answers) + remaining_questions(guide, answers)
            ),
        )

    roadmap = build_roadmap(
        guide, process, answers, sources=get_sources_config(), verification=get_verification()
    )
    if roadmap is None:
        return GuideResponse(
            durum="kaynak_yok",
            cevaplar=answers,
            mesaj=(
                "Bu durum için resmi kaynaklarda doğrulanmış bilgi bulunamadı. Lütfen "
                f"{process.referral} ile iletişime geçin."
            ),
        )
    return GuideResponse(durum="tamam", cevaplar=answers, yol_haritasi=roadmap)
