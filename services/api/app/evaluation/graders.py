"""Programatik puanlayıcılar (deterministik, ücretsiz).

Her metrik 0..1 arasında bir sayı ya da "ölçülemez" anlamında None döner. None değerler
ortalamaya katılmaz (ör. netleştirme cevabı beklenmeyen vakada cevap çıkarma oranı).
"""

import re

from app.evaluation.cases import Case, CaseSet, Element
from app.rag.schema import OUT_OF_SCOPE
from app.rag.understanding import MAX_QUESTIONS
from app.text import turkish_lower

_CIRCUMFLEX = str.maketrans({"â": "a", "î": "i", "û": "u", "Â": "a", "Î": "i", "Û": "u"})


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", turkish_lower(text.translate(_CIRCUMFLEX))).strip()


def roadmap_text(roadmap: dict) -> str:
    """Yol haritasının kullanıcıya görünen tüm metni (kaynak adresleri hariç)."""
    parts = [roadmap.get("ozet", "")]
    for step in roadmap.get("adimlar", []):
        parts += [step["baslik"], step["aciklama"], step["kurum"], step.get("tahmini_ucret") or ""]
        parts += step.get("gerekli_evraklar", [])
    parts += roadmap.get("uyarilar", [])
    return normalize(" \n ".join(parts))


def element_found(element: Element, text: str) -> bool:
    for equivalent in element.esdeger:
        terms = [equivalent] if isinstance(equivalent, str) else equivalent
        if all(normalize(term) in text for term in terms):
            return True
    return False


def grade_understanding(
    case: Case, *, status: str, process_code: str | None, answers: dict, questions: list
) -> dict[str, float | None]:
    predicted = OUT_OF_SCOPE if status == "out_of_scope" else process_code
    grade: dict[str, float | None] = {
        "islem_dogru": float(predicted == case.beklenen_islem),
        "soru_siniri": float(len(questions) <= MAX_QUESTIONS),
        "cevap_cikarma": None,
    }
    if case.beklenen_cevaplar:
        hits = sum(answers.get(k) == v for k, v in case.beklenen_cevaplar.items())
        grade["cevap_cikarma"] = hits / len(case.beklenen_cevaplar)
    return grade


def grade_roadmap(
    case: Case, case_set: CaseSet, *, status: str, roadmap: dict | None, dropped_steps: int
) -> tuple[dict[str, float | None], dict]:
    """Yol haritası metrikleri ve açıklama (karşılanmayan unsurlar)."""
    elements = {ref: case_set.unsurlar[ref] for ref in case.beklenen_unsurlar}
    if status != "ok" or not roadmap:
        grade = {
            "yol_haritasi": 0.0,
            "unsur_kapsama": 0.0,
            "evrak_kapsama": 0.0 if any(e.tur == "evrak" for e in elements.values()) else None,
            "kaynak_gosterme": None,
            "dogrulanan_adim": None,
        }
        return grade, {"karsilanmayan": list(elements)}

    text = roadmap_text(roadmap)
    found = {ref: element_found(el, text) for ref, el in elements.items()}
    documents = [ref for ref, el in elements.items() if el.tur == "evrak"]
    steps = roadmap.get("adimlar", [])
    kept = len(steps)
    grade = {
        "yol_haritasi": 1.0,
        "unsur_kapsama": sum(found.values()) / len(found) if found else None,
        "evrak_kapsama": (sum(found[r] for r in documents) / len(documents) if documents else None),
        # Yayın şemasında kaynaksız adım olamaz; bu metrik bir yapı hatasını yakalamak içindir.
        "kaynak_gosterme": sum(bool(s.get("kaynaklar")) for s in steps) / kept if kept else None,
        # Modelin ürettiği adımlardan kaynağa karşı doğrulanabilenlerin oranı
        "dogrulanan_adim": kept / (kept + dropped_steps) if kept + dropped_steps else None,
    }
    return grade, {"karsilanmayan": [ref for ref, ok in found.items() if not ok]}


def pii_leaked(case: Case, llm_requests: list[str]) -> float | None:
    """1.0 = vakadaki kişisel verilerden biri maskelenmeden LLM'e gitti."""
    if not case.kisisel_veriler:
        return None
    return float(any(item in request for item in case.kisisel_veriler for request in llm_requests))
