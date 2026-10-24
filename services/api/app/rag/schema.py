"""Şemalar.

İki katman vardır:
- LLM şemaları (`Llm*`): Modelin doldurduğu ara çıktı. Her adım ve uyarı, verilen kaynak
  parçalarına kimlikle (K1, K2...) ve birebir alıntıyla dayanmak zorundadır.
- Yayın şeması (`Roadmap`): Kullanıcıya dönen, proje belgesinde tanımlı JSON. Kaynak başlığı,
  adresi ve kontrol tarihi LLM'den değil veritabanından gelir.
"""

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["yuksek", "orta", "dusuk"]
OUT_OF_SCOPE = "kapsam_disi"


def _nullable_string() -> dict[str, object]:
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


def _object(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


# --- Soru anlama ---


class LlmAnswer(BaseModel):
    anahtar: str
    deger: str


class LlmUnderstanding(BaseModel):
    islem: str
    gerekce: str
    cevaplar: list[LlmAnswer]


def understanding_schema(process_codes: list[str], slot_keys: list[str]) -> dict[str, object]:
    answer = _object(
        {
            "anahtar": {"type": "string", "enum": slot_keys or ["yok"]},
            "deger": {"type": "string"},
        }
    )
    return _object(
        {
            "islem": {"type": "string", "enum": [*process_codes, OUT_OF_SCOPE]},
            "gerekce": {"type": "string"},
            "cevaplar": {"type": "array", "items": answer},
        }
    )


# --- Yol haritası (LLM ara çıktısı) ---


class LlmEvidence(BaseModel):
    kaynak: str  # "K3"
    alinti: str  # kaynaktan birebir alıntı


class LlmStep(BaseModel):
    baslik: str
    aciklama: str
    gerekli_evraklar: list[str]
    kurum: str
    tahmini_ucret: str | None
    dayanaklar: list[LlmEvidence]


class LlmWarning(BaseModel):
    metin: str
    dayanaklar: list[LlmEvidence]


class LlmRoadmap(BaseModel):
    yeterli_kaynak: bool
    ozet: str
    adimlar: list[LlmStep]
    uyarilar: list[LlmWarning]
    guven: Confidence


def roadmap_schema() -> dict[str, object]:
    evidence = _object({"kaynak": {"type": "string"}, "alinti": {"type": "string"}})
    evidence_list = {"type": "array", "items": evidence}
    step = _object(
        {
            "baslik": {"type": "string"},
            "aciklama": {"type": "string"},
            "gerekli_evraklar": {"type": "array", "items": {"type": "string"}},
            "kurum": {"type": "string"},
            "tahmini_ucret": _nullable_string(),
            "dayanaklar": evidence_list,
        }
    )
    warning = _object({"metin": {"type": "string"}, "dayanaklar": evidence_list})
    return _object(
        {
            "yeterli_kaynak": {"type": "boolean"},
            "ozet": {"type": "string"},
            "adimlar": {"type": "array", "items": step},
            "uyarilar": {"type": "array", "items": warning},
            "guven": {"type": "string", "enum": ["yuksek", "orta", "dusuk"]},
        }
    )


# --- Yayın şeması (proje belgesindeki biçim) ---


class SourceRef(BaseModel):
    baslik: str
    url: str
    son_kontrol: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class Step(BaseModel):
    sira: int = Field(ge=1)
    baslik: str
    aciklama: str
    gerekli_evraklar: list[str]
    kurum: str
    tahmini_ucret: str | None
    kaynaklar: list[SourceRef] = Field(min_length=1)


class Roadmap(BaseModel):
    islem: str
    ozet: str
    adimlar: list[Step] = Field(min_length=1)
    uyarilar: list[str]
    guven: Confidence
