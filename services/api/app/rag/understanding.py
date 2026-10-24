"""Soru anlama: işlem türü sınıflandırma ve netleştirici sorular (en fazla 3)."""

import json
import logging
from dataclasses import dataclass, field
from typing import Literal

from pydantic import ValidationError

from app.config import get_settings
from app.llm import LLMProvider
from app.privacy import mask_pii
from app.process_types import ProcessType, Slot
from app.rag.prompts import UNDERSTANDING_SYSTEM, retry_note, understanding_user_message
from app.rag.schema import OUT_OF_SCOPE, LlmUnderstanding, understanding_schema

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 3


class UnderstandingError(Exception):
    """Model iki denemede de geçerli bir yanıt üretemedi."""


@dataclass(frozen=True)
class Understanding:
    status: Literal["out_of_scope", "needs_clarification", "ready"]
    masked_text: str
    process: ProcessType | None = None
    answers: dict[str, str] = field(default_factory=dict)
    questions: list[Slot] = field(default_factory=list)


def valid_answers(process: ProcessType, answers: dict[str, str]) -> dict[str, str]:
    """Yalnızca bu işleme ait sorulara, tanımlı seçeneklerden biriyle verilmiş cevaplar kalır."""
    options = {s.key: set(s.options) for s in process.slots}
    return {k: v for k, v in answers.items() if v in options.get(k, set())}


def _with_questions(masked: str, process: ProcessType, answers: dict[str, str]) -> Understanding:
    missing = [s for s in process.slots if s.key not in answers][:MAX_QUESTIONS]
    return Understanding(
        status="needs_clarification" if missing else "ready",
        masked_text=masked,
        process=process,
        answers=answers,
        questions=missing,
    )


def understand(
    text: str,
    *,
    llm: LLMProvider,
    process_types: list[ProcessType],
    process_code: str | None = None,
    answers: dict[str, str] | None = None,
) -> Understanding:
    masked = mask_pii(text).text
    given = answers or {}

    # İkinci tur: işlem zaten belli; kullanıcının seçtiği cevaplarla eksik sorular hesaplanır.
    if process_code:
        process = next((p for p in process_types if p.code == process_code), None)
        if process is None:
            raise ValueError(f"Bilinmeyen işlem kodu: {process_code}")
        return _with_questions(masked, process, valid_answers(process, given))

    schema = understanding_schema(
        [p.code for p in process_types],
        sorted({s.key for p in process_types for s in p.slots}),
    )
    user = understanding_user_message(masked, process_types)
    parsed: LlmUnderstanding | None = None
    error = ""
    for attempt in range(2):
        response = llm.generate_json(
            system=UNDERSTANDING_SYSTEM,
            user=user + (retry_note(error) if attempt else ""),
            schema=schema,
            # Düşünme `max_tokens`'a dahildir; kısa yanıt için bile pay bırakılır.
            max_tokens=16000,
            effort=get_settings().llm_understanding_effort,
        )
        try:
            parsed = LlmUnderstanding.model_validate(json.loads(response.text))
            break
        except (json.JSONDecodeError, ValidationError) as exc:
            error = type(exc).__name__
            logger.warning("Sınıflandırma yanıtı şemaya uymadı (deneme %d)", attempt + 1)
    if parsed is None:
        raise UnderstandingError("Sınıflandırma yanıtı doğrulanamadı")

    process = next((p for p in process_types if p.code == parsed.islem), None)
    if parsed.islem == OUT_OF_SCOPE or process is None:
        return Understanding(status="out_of_scope", masked_text=masked)

    extracted = valid_answers(process, {a.anahtar: a.deger for a in parsed.cevaplar})
    return _with_questions(masked, process, extracted | valid_answers(process, given))
