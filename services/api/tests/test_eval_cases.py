"""eval/cases.yaml için programatik denetimler (tüm set üzerinde)."""

from app.evaluation.cases import Case, CaseSet, Element, load_case_set, validate_case_set
from app.process_types import get_process_types


def test_repository_case_set_is_consistent() -> None:
    case_set = load_case_set()
    assert validate_case_set(case_set, list(get_process_types())) == []


def test_every_element_is_used_and_sourced() -> None:
    case_set = load_case_set()
    used = {ref for c in case_set.vakalar for ref in c.beklenen_unsurlar}
    assert set(case_set.unsurlar) == used
    assert all("«" in el.kaynak for el in case_set.unsurlar.values())


def test_both_directions_and_special_cases_are_covered() -> None:
    case_set = load_case_set()
    tags = {t for c in case_set.vakalar for t in c.etiketler}
    assert {"kapsam_disi", "kisisel_veri", "enjeksiyon", "kaynak_yetersiz", "zor"} <= tags
    assert sum(c.has_roadmap for c in case_set.vakalar) >= 20


def test_validator_reports_problems() -> None:
    element = Element(ad="X", tur="evrak", esdeger=["x"], kaynak="Bir kaynak alıntısı")
    case_set = CaseSet(
        surum=1,
        unsurlar={"x": element},
        vakalar=[
            Case(id="a", etiketler=["pasaport"], metin="aynı metin", beklenen_islem="pasaport"),
            Case(id="a", etiketler=["pasaport"], metin="Aynı  metin", beklenen_islem="pasaport"),
            Case(
                id="b",
                etiketler=["miras_arac_devri"],
                metin="abc",
                beklenen_islem="miras_arac_devri",
                cevaplar={"kisitlama": "Belki"},
                beklenen_unsurlar=["yok"],
            ),
        ],
    )
    problems = "\n".join(validate_case_set(case_set, list(get_process_types())))
    assert "Tekrarlanan vaka kimliği: a" in problems
    assert "Tekrarlanan vaka metni" in problems
    assert "tanımsız unsur yok" in problems
    assert "geçersiz seçenek 'Belki'" in problems
    assert "Kapsam dışı vaka sayısı az" in problems
