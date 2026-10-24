from app.evaluation.cases import Element, load_case_set
from app.evaluation.graders import (
    element_found,
    grade_roadmap,
    grade_understanding,
    normalize,
    pii_leaked,
    roadmap_text,
)

CASE_SET = load_case_set()
CASE = next(c for c in CASE_SET.vakalar if c.id == "miras_arac_01")


def roadmap(texts: list[str], steps: int = 1) -> dict:
    return {
        "islem": "miras_arac_devri",
        "ozet": " ".join(texts),
        "adimlar": [
            {
                "sira": i + 1,
                "baslik": f"Adım {i + 1}",
                "aciklama": "",
                "gerekli_evraklar": [],
                "kurum": "",
                "tahmini_ucret": None,
                "kaynaklar": [
                    {"baslik": "K", "url": "https://x.gov.tr", "son_kontrol": "2026-10-24"}
                ],
            }
            for i in range(steps)
        ],
        "uyarilar": [],
        "guven": "yuksek",
    }


def test_oracle_roadmap_scores_full_coverage() -> None:
    """Kâhin: her beklenen unsurun ilk eşdeğerini içeren yol haritası %100 almalı."""
    texts = []
    for ref in CASE.beklenen_unsurlar:
        first = CASE_SET.unsurlar[ref].esdeger[0]
        texts.append(first if isinstance(first, str) else " ".join(first))
    grade, explain = grade_roadmap(
        CASE, CASE_SET, status="ok", roadmap=roadmap(texts), dropped_steps=0
    )
    assert grade["unsur_kapsama"] == 1.0
    assert grade["evrak_kapsama"] == 1.0
    assert grade["kaynak_gosterme"] == 1.0
    assert explain["karsilanmayan"] == []


def test_null_roadmap_scores_zero() -> None:
    grade, _ = grade_roadmap(
        CASE, CASE_SET, status="ok", roadmap=roadmap(["Lütfen kuruma başvurun."]), dropped_steps=0
    )
    assert grade["unsur_kapsama"] == 0.0


def test_no_roadmap_counts_as_zero_coverage_not_missing() -> None:
    grade, explain = grade_roadmap(
        CASE, CASE_SET, status="no_sources", roadmap=None, dropped_steps=0
    )
    assert grade["yol_haritasi"] == 0.0 and grade["unsur_kapsama"] == 0.0
    assert set(explain["karsilanmayan"]) == set(CASE.beklenen_unsurlar)


def test_dropped_steps_lower_verified_ratio() -> None:
    grade, _ = grade_roadmap(
        CASE, CASE_SET, status="ok", roadmap=roadmap(["x"], steps=3), dropped_steps=1
    )
    assert grade["dogrulanan_adim"] == 0.75


def test_matching_ignores_case_turkish_letters_and_circumflex() -> None:
    element = Element(ad="v", tur="evrak", esdeger=["vekaletname"], kaynak="«alıntı» kaynak")
    assert element_found(element, normalize("VEKÂLETNAME getirin"))
    assert normalize("İLİŞİK KESME") == "ilişik kesme"


def test_all_of_equivalents_require_every_term() -> None:
    element = Element(
        ad="m", tur="evrak", esdeger=[["miras bırakan", "kimlik numara"]], kaynak="«x» kaynak"
    )
    assert element_found(element, normalize("Miras bırakanın T.C. kimlik numarası"))
    assert not element_found(element, normalize("Miras bırakanın ölüm belgesi"))


def test_roadmap_text_covers_steps_documents_and_warnings() -> None:
    data = roadmap(["özet"])
    data["adimlar"][0]["gerekli_evraklar"] = ["Ruhsat"]
    data["uyarilar"] = ["90 gün içinde başvurun"]
    text = roadmap_text(data)
    assert "ruhsat" in text and "90 gün" in text


def test_understanding_grades() -> None:
    case = next(c for c in CASE_SET.vakalar if c.id == "miras_arac_02")
    grade = grade_understanding(
        case,
        status="needs_clarification",
        process_code="miras_arac_devri",
        answers={"mirascilik_belgesi": "Evet"},
        questions=[1, 2],
    )
    assert grade == {"islem_dogru": 1.0, "soru_siniri": 1.0, "cevap_cikarma": 0.5}

    out_case = next(c for c in CASE_SET.vakalar if c.id == "kapsam_disi_01")
    assert (
        grade_understanding(
            out_case, status="out_of_scope", process_code=None, answers={}, questions=[]
        )["islem_dogru"]
        == 1.0
    )
    assert (
        grade_understanding(
            out_case, status="ready", process_code="miras_arac_devri", answers={}, questions=[]
        )["islem_dogru"]
        == 0.0
    )


def test_pii_leak_detection() -> None:
    case = next(c for c in CASE_SET.vakalar if c.id == "miras_arac_09")
    assert pii_leaked(case, ["TC [TC_KIMLIK], plaka [PLAKA]"]) == 0.0
    assert pii_leaked(case, ["plaka 34 ABC 123"]) == 1.0
    assert pii_leaked(CASE, ["herhangi"]) is None
