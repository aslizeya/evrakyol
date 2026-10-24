"""Vaka setinin yüklenmesi ve tutarlılık denetimi."""

import hashlib
from collections import Counter
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from app.config import REPO_ROOT
from app.process_types import ProcessType
from app.rag.schema import OUT_OF_SCOPE

DEFAULT_CASES = REPO_ROOT / "eval" / "cases.yaml"
MIN_CASES_PER_PROCESS = 10
MIN_OUT_OF_SCOPE = 10

# Bir eşdeğer ifade ya tek bir metindir ya da hepsinin geçmesi gereken metinler listesidir.
Equivalent = str | list[str]


class Element(BaseModel):
    ad: str
    tur: Literal["evrak", "kurum", "uyari", "bilgi"]
    esdeger: list[Equivalent] = Field(min_length=1)
    kaynak: str = Field(min_length=10)


class Case(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    etiketler: list[str] = Field(min_length=1)
    metin: str = Field(min_length=3)
    beklenen_islem: str
    beklenen_cevaplar: dict[str, str] = {}
    cevaplar: dict[str, str] = {}
    beklenen_unsurlar: list[str] = []
    kisisel_veriler: list[str] = []
    dogrulandi: bool = False

    @property
    def has_roadmap(self) -> bool:
        return bool(self.beklenen_unsurlar)

    @property
    def group(self) -> str:
        return self.etiketler[0]


class CaseSet(BaseModel):
    surum: int
    unsurlar: dict[str, Element]
    vakalar: list[Case]


def load_case_set(path: Path = DEFAULT_CASES) -> CaseSet:
    return CaseSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_case_set(case_set: CaseSet, process_types: list[ProcessType]) -> list[str]:
    """Vaka setindeki tutarsızlıkları döndürür (boş liste = sorun yok)."""
    problems: list[str] = []
    by_code = {p.code: p for p in process_types}
    ids = Counter(c.id for c in case_set.vakalar)
    problems += [f"Tekrarlanan vaka kimliği: {i}" for i, n in ids.items() if n > 1]
    texts = Counter(" ".join(c.metin.casefold().split()) for c in case_set.vakalar)
    problems += [f"Tekrarlanan vaka metni: {t!r}" for t, n in texts.items() if n > 1]

    for case in case_set.vakalar:
        if case.beklenen_islem != OUT_OF_SCOPE and case.beklenen_islem not in by_code:
            problems.append(f"{case.id}: bilinmeyen işlem kodu {case.beklenen_islem}")
            continue
        if case.group != case.beklenen_islem:
            problems.append(f"{case.id}: ilk etiket beklenen işlemle aynı olmalı")
        for ref in case.beklenen_unsurlar:
            if ref not in case_set.unsurlar:
                problems.append(f"{case.id}: tanımsız unsur {ref}")
        process = by_code.get(case.beklenen_islem)
        for field_name in ("beklenen_cevaplar", "cevaplar"):
            for key, value in getattr(case, field_name).items():
                slot = next((s for s in process.slots if s.key == key), None) if process else None
                if slot is None:
                    problems.append(f"{case.id}: {field_name} içinde bilinmeyen soru {key}")
                elif value not in slot.options:
                    problems.append(f"{case.id}: {key} için geçersiz seçenek {value!r}")
        if case.has_roadmap and process and process.slots and not case.cevaplar:
            problems.append(f"{case.id}: yol haritası vakası netleştirme cevaplarını içermeli")
        for item in case.kisisel_veriler:
            if item not in case.metin:
                problems.append(f"{case.id}: kişisel veri metinde geçmiyor: {item!r}")

    counts = Counter(c.beklenen_islem for c in case_set.vakalar)
    for code in by_code:
        if counts[code] < MIN_CASES_PER_PROCESS:
            problems.append(f"{code}: {counts[code]} vaka (en az {MIN_CASES_PER_PROCESS})")
    if counts[OUT_OF_SCOPE] < MIN_OUT_OF_SCOPE:
        problems.append(f"Kapsam dışı vaka sayısı az: {counts[OUT_OF_SCOPE]}")
    return problems
