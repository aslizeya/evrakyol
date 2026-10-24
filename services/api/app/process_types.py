import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class Slot(BaseModel):
    """Netleştirici soru. Yol haritasını değiştiren, kişisel veri içermeyen bir bilgi."""

    key: str = Field(pattern=r"^[a-z_]+$")
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=2)


class ProcessType(BaseModel):
    code: str = Field(pattern=r"^[a-z_]+$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    # Kaynak bulunamadığında kullanıcının yönlendirileceği kurum
    referral: str = Field(min_length=1)
    slots: list[Slot] = []


def load_process_types(config_dir: Path) -> list[ProcessType]:
    """config/process_types.json dosyasını okur (web tarafıyla ortak kaynak)."""
    raw = json.loads((config_dir / "process_types.json").read_text(encoding="utf-8"))
    return [ProcessType.model_validate(item) for item in raw["process_types"]]


@lru_cache
def get_process_types() -> tuple[ProcessType, ...]:
    from app.config import get_settings

    return tuple(load_process_types(get_settings().config_dir))


def get_process_type(code: str) -> ProcessType | None:
    return next((p for p in get_process_types() if p.code == code), None)
