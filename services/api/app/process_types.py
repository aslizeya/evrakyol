import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from app.config import get_settings


class ProcessType(BaseModel):
    code: str = Field(pattern=r"^[a-z_]+$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


def load_process_types(config_dir: Path) -> list[ProcessType]:
    """config/process_types.json dosyasını okur (web tarafıyla ortak kaynak)."""
    raw = json.loads((config_dir / "process_types.json").read_text(encoding="utf-8"))
    return [ProcessType.model_validate(item) for item in raw["process_types"]]


@lru_cache
def get_process_types() -> tuple[ProcessType, ...]:
    return tuple(load_process_types(get_settings().config_dir))
