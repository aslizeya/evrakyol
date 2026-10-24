"""Sorularla ilerleyen rehber: yapay zekâ olmadan, önceden hazırlanmış ve kaynakla doğrulanmış
içerikten yol haritası oluşturur.

İçerik `config/rehber/<islem>.yaml` dosyalarındadır. Her adım ve uyarı resmi bir kaynaktan birebir
alıntıya dayanır; alıntılar `python -m app.rehber kontrol` ile kaynağın güncel metninde aranır ve
sonuç `config/rehber/dogrulama.json` dosyasına yazılır. Çalışma anında yalnızca son kontrolde
alıntıları bulunan adımlar gösterilir: kaynak sayfası değişip alıntı kaybolursa adım kendiliğinden
gizlenir ("kaynaksız bilgi yok" ilkesi).

Kullanıcıdan yalnızca seçenekli cevaplar alınır; serbest metin ve kişisel veri istenmez.
"""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from app.ingest.sources_config import SourcesConfig, get_sources_config
from app.process_types import ProcessType, Slot, get_process_types
from app.rag.roadmap import STALE_AFTER, _normalize
from app.rag.schema import Confidence, Roadmap, SourceRef, Step

NOT_ASKED = "(sorulmadı)"
VERIFICATION_FILE = "dogrulama.json"

UNAPPROVED_WARNING = (
    "Bu rehberin içeriği henüz uzman onayından geçmemiştir; işlem öncesinde ilgili kurumdan "
    "teyit ediniz."
)
HIDDEN_STEPS_WARNING = (
    "{n} adım, dayandığı resmi kaynak metninde son kontrolde doğrulanamadığı için gösterilmedi. "
    "İşlemin tamamı için {referral} ile görüşünüz."
)

# Koşul: {soru_anahtari: [kabul edilen cevaplar]} (hepsi sağlanmalı) veya bunların listesi
# (herhangi biri sağlanmalı).
Condition = dict[str, list[str]] | list[dict[str, list[str]]]


class Evidence(BaseModel):
    kaynak: str
    alinti: str = Field(min_length=12)

    @property
    def key(self) -> str:
        """Alıntı kimliği: kaynak + normalize metin. Metin değişirse yeniden doğrulanır."""
        raw = f"{self.kaynak}\n{_normalize(self.alinti)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class GuideQuestion(BaseModel):
    anahtar: str
    sor_eger: Condition | None = None


class GuideStep(BaseModel):
    id: str = Field(pattern=r"^[a-z_]+$")
    goster_eger: Condition | None = None
    baslik: str
    aciklama: str
    gerekli_evraklar: list[str] = []
    kurum: str
    tahmini_ucret: str | None = None
    dayanaklar: list[Evidence] = Field(min_length=1)


class GuideWarning(BaseModel):
    goster_eger: Condition | None = None
    metin: str
    dayanaklar: list[Evidence] = Field(min_length=1)


class GuideNote(BaseModel):
    """Kaynakta karşılığı olmayan durum: bilgi vermez, yalnızca kuruma yönlendirir."""

    goster_eger: Condition | None = None
    metin: str


class Guide(BaseModel):
    islem: str
    onaylandi: bool = False
    ozet: str
    sorular: list[GuideQuestion] = Field(min_length=1)
    adimlar: list[GuideStep] = Field(min_length=1)
    uyarilar: list[GuideWarning] = []
    notlar: list[GuideNote] = []

    @model_validator(mode="after")
    def _unique_ids(self) -> "Guide":
        ids = [s.id for s in self.adimlar]
        if len(ids) != len(set(ids)):
            raise ValueError("adım kimlikleri tekrarlanıyor")
        return self

    def evidence(self) -> list[Evidence]:
        items = [e for s in self.adimlar for e in s.dayanaklar]
        return items + [e for w in self.uyarilar for e in w.dayanaklar]

    def conditions(self) -> list[Condition]:
        found = [q.sor_eger for q in self.sorular]
        found += [x.goster_eger for x in [*self.adimlar, *self.uyarilar, *self.notlar]]
        return [c for c in found if c is not None]


class GuideError(ValueError):
    pass


# --- yükleme ve tutarlılık denetimi ---


def _condition_parts(condition: Condition) -> list[dict[str, list[str]]]:
    return condition if isinstance(condition, list) else [condition]


def validate_guide(guide: Guide, process: ProcessType, sources: SourcesConfig) -> None:
    """İçerik dosyasının soru ve kaynak tanımlarıyla tutarlı olduğunu denetler."""
    slots = {s.key: s for s in process.slots}
    asked = [q.anahtar for q in guide.sorular]
    if len(asked) != len(set(asked)):
        raise GuideError(f"{guide.islem}: aynı soru birden çok kez soruluyor")
    for key in asked:
        if key not in slots:
            raise GuideError(f"{guide.islem}: bilinmeyen soru '{key}'")
    for condition in guide.conditions():
        for part in _condition_parts(condition):
            for key, values in part.items():
                if key not in asked:
                    raise GuideError(f"{guide.islem}: koşulda sorulmayan soru '{key}'")
                unknown = set(values) - set(slots[key].options) - {NOT_ASKED}
                if unknown:
                    raise GuideError(
                        f"{guide.islem}: '{key}' için geçersiz cevap {sorted(unknown)}"
                    )
    seeds = {s.url for s in sources.sources if guide.islem in s.process_codes}
    for item in guide.evidence():
        if item.kaynak not in seeds:
            raise GuideError(
                f"{guide.islem}: '{item.kaynak}' bu işlemin kaynak listesinde (sources.yaml) yok"
            )


def load_guides(
    directory: Path, process_types: tuple[ProcessType, ...], sources: SourcesConfig
) -> dict[str, Guide]:
    guides: dict[str, Guide] = {}
    by_code = {p.code: p for p in process_types}
    for path in sorted(directory.glob("*.yaml")):
        guide = Guide.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if guide.islem != path.stem:
            raise GuideError(f"{path.name}: dosya adı işlem koduyla aynı olmalı")
        process = by_code.get(guide.islem)
        if process is None:
            raise GuideError(f"{path.name}: bilinmeyen işlem kodu")
        validate_guide(guide, process, sources)
        guides[guide.islem] = guide
    return guides


def guides_dir() -> Path:
    from app.config import get_settings

    return get_settings().config_dir / "rehber"


@lru_cache
def get_guides() -> dict[str, Guide]:
    return load_guides(guides_dir(), get_process_types(), get_sources_config())


# --- doğrulama kaydı ---


class SourceCheck(BaseModel):
    son_kontrol: str | None = None  # son başarılı çekimin tarihi (YYYY-AA-GG)
    durum: str = "kontrol_edilmedi"


class Verification(BaseModel):
    kaynaklar: dict[str, SourceCheck] = {}
    # alıntı kimliği -> son başarılı kontrolde kaynakta bulundu mu
    alintilar: dict[str, bool] = {}

    def is_verified(self, item: Evidence) -> bool:
        checked = self.kaynaklar.get(item.kaynak, SourceCheck()).son_kontrol
        return bool(checked) and self.alintilar.get(item.key, False)


def load_verification(directory: Path) -> Verification:
    path = directory / VERIFICATION_FILE
    if not path.exists():
        return Verification()
    return Verification.model_validate(json.loads(path.read_text(encoding="utf-8")))


@lru_cache
def get_verification() -> Verification:
    return load_verification(guides_dir())


# --- akış ---


def matches(condition: Condition | None, answers: dict[str, str]) -> bool:
    if condition is None:
        return True
    return any(
        all(answers.get(key, NOT_ASKED) in values for key, values in part.items())
        for part in _condition_parts(condition)
    )


def effective_answers(
    guide: Guide, process: ProcessType, answers: dict[str, str]
) -> dict[str, str]:
    """Sırayla sorulabilecek soruların geçerli cevapları. Geri dönülüp bir cevap değiştirildiğinde
    artık sorulmayacak soruların eski cevapları düşer."""
    slots = {s.key: s for s in process.slots}
    result: dict[str, str] = {}
    for question in guide.sorular:
        if not matches(question.sor_eger, result):
            continue
        value = answers.get(question.anahtar)
        if value is None:
            break
        if value not in slots[question.anahtar].options:
            break
        result[question.anahtar] = value
    return result


def next_question(guide: Guide, process: ProcessType, answers: dict[str, str]) -> Slot | None:
    slots = {s.key: s for s in process.slots}
    for question in guide.sorular:
        if question.anahtar not in answers and matches(question.sor_eger, answers):
            return slots[question.anahtar]
    return None


def remaining_questions(guide: Guide, answers: dict[str, str]) -> int:
    """Kalan soru sayısı (tahmini: henüz cevaplanmamış koşullar 'sorulmadı' sayılır)."""
    return sum(
        1 for q in guide.sorular if q.anahtar not in answers and matches(q.sor_eger, answers)
    )


def _source_ref(url: str, sources: SourcesConfig, verification: Verification) -> SourceRef:
    seed = next(s for s in sources.sources if s.url == url)
    checked = verification.kaynaklar.get(url, SourceCheck()).son_kontrol
    return SourceRef(baslik=seed.title or url, url=url, son_kontrol=checked or "")


def build_roadmap(
    guide: Guide,
    process: ProcessType,
    answers: dict[str, str],
    *,
    sources: SourcesConfig,
    verification: Verification,
    today: date | None = None,
) -> Roadmap | None:
    """Cevaplara uyan ve dayanakları doğrulanmış adımlardan yol haritası. Gösterilecek adım
    kalmazsa None döner (kullanıcı kuruma yönlendirilir)."""
    today = today or datetime.now(UTC).date()
    steps: list[Step] = []
    hidden = 0
    cited: set[str] = set()
    for item in guide.adimlar:
        if not matches(item.goster_eger, answers):
            continue
        if not all(verification.is_verified(e) for e in item.dayanaklar):
            hidden += 1
            continue
        urls = list(dict.fromkeys(e.kaynak for e in item.dayanaklar))
        cited.update(urls)
        steps.append(
            Step(
                sira=len(steps) + 1,
                baslik=item.baslik,
                aciklama=item.aciklama,
                gerekli_evraklar=item.gerekli_evraklar,
                kurum=item.kurum,
                tahmini_ucret=item.tahmini_ucret,
                kaynaklar=[_source_ref(u, sources, verification) for u in urls],
            )
        )
    if not steps:
        return None

    warnings = [
        w.metin
        for w in guide.uyarilar
        if matches(w.goster_eger, answers)
        and all(verification.is_verified(e) for e in w.dayanaklar)
    ]
    notes = [n.metin for n in guide.notlar if matches(n.goster_eger, answers)]
    warnings += notes
    if hidden:
        warnings.append(HIDDEN_STEPS_WARNING.format(n=hidden, referral=process.referral))
    stale = sorted(
        _source_ref(u, sources, verification).baslik
        for u in cited
        if _is_stale(verification.kaynaklar.get(u), today)
    )
    if stale:
        warnings.append(
            "Şu kaynaklar 30 günden uzun süredir yeniden kontrol edilmedi: " + ", ".join(stale)
        )
    if not guide.onaylandi:
        warnings.append(UNAPPROVED_WARNING)

    # Onay durumu güveni değil, uyarıyı belirler: "orta" güven, kaynaklarda eksik kalan bir durum
    # (gizlenen adım, kuruma yönlendirme notu, eski kaynak) olduğunu anlatır.
    confidence: Confidence = "orta" if hidden or notes or stale else "yuksek"
    return Roadmap(
        islem=guide.islem, ozet=guide.ozet, adimlar=steps, uyarilar=warnings, guven=confidence
    )


def _is_stale(check: SourceCheck | None, today: date) -> bool:
    if check is None or not check.son_kontrol:
        return True
    return today - date.fromisoformat(check.son_kontrol) > timedelta(days=STALE_AFTER.days)
