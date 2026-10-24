"""Kaynak dayanaklı yol haritası üretimi ve doğrulaması.

"Kaynaksız bilgi yok" ilkesi burada uygulanır:
1. LLM'e yalnızca getirilen kaynak parçaları verilir.
2. LLM her adım ve uyarı için kaynak kimliği + birebir alıntı vermek zorundadır.
3. Sunucu, alıntının gerçekten o parçada geçtiğini kontrol eder. Doğrulanamayan adım veya
   uyarı çıkarılır; kaynakta geçmeyen ücret silinir.
4. Kaynak başlığı, adresi ve kontrol tarihi LLM'den değil veritabanından eklenir.
5. Yanıt şemaya uymazsa bir kez daha denenir; yine uymazsa hata verilir, uydurma yapılmaz.
"""

import html
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import ValidationError

from app.llm import LLMProvider
from app.privacy import mask_pii
from app.process_types import ProcessType
from app.rag.prompts import ROADMAP_SYSTEM, retry_note, roadmap_user_message
from app.rag.retrieval import RetrievedChunk, Retriever
from app.rag.schema import (
    Confidence,
    LlmEvidence,
    LlmRoadmap,
    Roadmap,
    SourceRef,
    Step,
    roadmap_schema,
)
from app.text import turkish_lower

logger = logging.getLogger(__name__)

MIN_QUOTE_CHARS = 12
STALE_AFTER = timedelta(days=30)
_CONFIDENCE_ORDER: list[Confidence] = ["dusuk", "orta", "yuksek"]


# Sistemin (LLM'in değil) eklediği uyarıların ayırt edici ifadeleri
SYSTEM_WARNING_MARKERS = (
    "ücret bilgisi kaynakta doğrulanamadığından",
    "resmi kaynakta doğrulanamadığı için yol haritasına eklenmedi",
    "30 günden uzun süredir yeniden kontrol edilmedi",
)


def is_system_warning(text: str) -> bool:
    return any(marker in text for marker in SYSTEM_WARNING_MARKERS)


class RoadmapGenerationError(Exception):
    """Model iki denemede de şemaya uygun yanıt üretemedi."""


@dataclass(frozen=True)
class RoadmapOutcome:
    status: Literal["ok", "no_sources"]
    masked_text: str
    roadmap: Roadmap | None = None
    referral: str | None = None
    dropped_steps: int = 0
    dropped_warnings: int = 0
    model: str | None = None
    source_ids: list[int] = field(default_factory=list)
    # Modele verilen kaynak parçaları (K1, K2... sırasıyla); değerlendirmede uydurma kontrolü için
    context: list[RetrievedChunk] = field(default_factory=list)


# --- alıntı doğrulama ---

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})


def _normalize(text: str) -> str:
    text = turkish_lower(html.unescape(text).translate(_QUOTES))
    return re.sub(r"\s+", " ", text).strip()


def quote_found(quote: str, chunk: RetrievedChunk) -> bool:
    """Alıntı (üç nokta ile bölünmüş parçalar dahil) parçanın metninde birebir geçiyor mu?"""
    haystack = _normalize(f"{chunk.heading_path or ''} {chunk.content}")
    parts = [p.strip(" .,;:\"'") for p in re.split(r"\.\.\.|…", _normalize(quote))]
    parts = [p for p in parts if p]
    if not parts or sum(len(p) for p in parts) < MIN_QUOTE_CHARS:
        return False
    position = 0
    for part in parts:
        index = haystack.find(part, position)
        if index < 0:
            return False
        position = index + len(part)
    return True


def _verified_chunks(
    evidence: list[LlmEvidence], by_id: dict[str, RetrievedChunk]
) -> list[RetrievedChunk]:
    verified: list[RetrievedChunk] = []
    for item in evidence:
        chunk = by_id.get(item.kaynak.strip().upper())
        if chunk and quote_found(item.alinti, chunk) and chunk not in verified:
            verified.append(chunk)
    return verified


_NUMBER = re.compile(r"\d[\d.,]*\d|\d")


def _digits(text: str) -> str:
    return re.sub(r"(?<=\d)[.,\s](?=\d)", "", text)


def fee_supported(fee: str, chunks: list[RetrievedChunk]) -> bool:
    """Ücretteki her sayı (ya da 'ücretsiz' ifadesi) dayanak parçalarda geçmeli."""
    haystack = _digits(_normalize(" ".join(c.content for c in chunks)))
    numbers = [_digits(n) for n in _NUMBER.findall(fee)]
    if not numbers:
        return "ücretsiz" in _normalize(fee) and "ücretsiz" in haystack
    return all(re.search(rf"(?<!\d){re.escape(n)}(?!\d)", haystack) for n in numbers)


# --- servis ---


def _lower_confidence(a: Confidence, b: Confidence) -> Confidence:
    return min(a, b, key=_CONFIDENCE_ORDER.index)


def _source_ref(chunk: RetrievedChunk) -> SourceRef:
    checked = chunk.last_fetched_at or datetime.now(UTC)
    return SourceRef(
        baslik=chunk.source_title, url=chunk.url, son_kontrol=checked.date().isoformat()
    )


def _unique_refs(chunks: list[RetrievedChunk]) -> list[SourceRef]:
    refs: dict[int, SourceRef] = {}
    for chunk in chunks:
        refs.setdefault(chunk.source_id, _source_ref(chunk))
    return list(refs.values())


class RoadmapService:
    def __init__(self, retriever: Retriever, llm: LLMProvider, *, top_k: int = 12):
        self.retriever = retriever
        self.llm = llm
        self.top_k = top_k

    def build(self, text: str, process: ProcessType, answers: dict[str, str]) -> RoadmapOutcome:
        masked = mask_pii(text).text
        query = " ".join([process.name, masked, *answers.values()])
        chunks = self.retriever.search(query, process.code, limit=self.top_k)
        if not chunks:
            return RoadmapOutcome("no_sources", masked, referral=process.referral)

        draft, model = self._generate(masked, process, answers, chunks)
        by_id = {f"K{i}": c for i, c in enumerate(chunks, start=1)}
        now = datetime.now(UTC)

        steps: list[Step] = []
        system_warnings: list[str] = []
        cited: list[RetrievedChunk] = []
        dropped = 0
        for llm_step in draft.adimlar:
            sources = _verified_chunks(llm_step.dayanaklar, by_id)
            if not sources:
                dropped += 1
                continue
            fee = llm_step.tahmini_ucret
            if fee and not fee_supported(fee, sources):
                system_warnings.append(
                    f"“{llm_step.baslik}” adımı için ücret bilgisi kaynakta doğrulanamadığından "
                    "gösterilmedi; ilgili kurumdan öğreniniz."
                )
                fee = None
            cited.extend(sources)
            steps.append(
                Step(
                    sira=len(steps) + 1,
                    baslik=llm_step.baslik,
                    aciklama=llm_step.aciklama,
                    gerekli_evraklar=llm_step.gerekli_evraklar,
                    kurum=llm_step.kurum,
                    tahmini_ucret=fee,
                    kaynaklar=_unique_refs(sources),
                )
            )

        # Kaynaktan gelen uyarılar önce, sistemin eklediği uyarılar sonra gösterilir.
        warnings: list[str] = []
        dropped_warnings = 0
        for warning in draft.uyarilar:
            if _verified_chunks(warning.dayanaklar, by_id):
                warnings.append(warning.metin)
            else:
                dropped_warnings += 1
        warnings.extend(system_warnings)

        if not steps:
            return RoadmapOutcome(
                "no_sources",
                masked,
                referral=process.referral,
                dropped_steps=dropped,
                dropped_warnings=dropped_warnings,
                model=model,
                context=chunks,
            )

        if dropped:
            warnings.append(
                f"{dropped} adım resmi kaynakta doğrulanamadığı için yol haritasına eklenmedi. "
                f"İşlemin tamamı için {process.referral} ile görüşünüz."
            )
        stale = sorted(
            {
                c.source_title
                for c in cited
                if c.last_fetched_at and now - c.last_fetched_at > STALE_AFTER
            }
        )
        if stale:
            warnings.append(
                "Şu kaynaklar 30 günden uzun süredir yeniden kontrol edilmedi: " + ", ".join(stale)
            )

        computed: Confidence = "yuksek"
        if dropped:
            computed = "orta" if dropped < len(draft.adimlar) / 2 else "dusuk"
        if not draft.yeterli_kaynak:
            computed = _lower_confidence(computed, "orta")

        roadmap = Roadmap(
            islem=process.code,
            ozet=draft.ozet,
            adimlar=steps,
            uyarilar=warnings,
            guven=_lower_confidence(draft.guven, computed),
        )
        return RoadmapOutcome(
            "ok",
            masked,
            roadmap=roadmap,
            dropped_steps=dropped,
            dropped_warnings=dropped_warnings,
            model=model,
            source_ids=sorted({c.source_id for c in cited}),
            context=chunks,
        )

    def _generate(
        self,
        masked: str,
        process: ProcessType,
        answers: dict[str, str],
        chunks: list[RetrievedChunk],
    ) -> tuple[LlmRoadmap, str]:
        user = roadmap_user_message(text=masked, process=process, answers=answers, chunks=chunks)
        error = ""
        for attempt in range(2):
            response = self.llm.generate_json(
                system=ROADMAP_SYSTEM,
                user=user + (retry_note(error) if attempt else ""),
                schema=roadmap_schema(),
            )
            try:
                return LlmRoadmap.model_validate(json.loads(response.text)), response.model
            except (json.JSONDecodeError, ValidationError) as exc:
                error = type(exc).__name__
                logger.warning("Yol haritası yanıtı şemaya uymadı (deneme %d)", attempt + 1)
        raise RoadmapGenerationError("Yol haritası yanıtı iki denemede de doğrulanamadı")
