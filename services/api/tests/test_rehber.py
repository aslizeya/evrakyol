"""Sorularla ilerleyen rehber: içerik tutarlılığı, akış kuralları ve uç nokta."""

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.ingest.sources_config import get_sources_config
from app.main import app
from app.process_types import get_process_type, get_process_types
from app.rehber import (
    NOT_ASKED,
    UNAPPROVED_WARNING,
    Evidence,
    Guide,
    GuideError,
    SourceCheck,
    Verification,
    build_roadmap,
    effective_answers,
    get_guides,
    get_verification,
    matches,
    next_question,
    validate_guide,
)

AUTH = {"Authorization": "Bearer test-anahtari"}
MIRAS = get_process_type("miras_arac_devri")
BELGE = get_process_type("mirascilik_belgesi")
SOURCES = get_sources_config()


def roadmap(code: str, answers: dict[str, str], verification: Verification | None = None):
    guide = get_guides()[code]
    process = get_process_type(code)
    return build_roadmap(
        guide,
        process,
        answers,
        sources=SOURCES,
        verification=verification or get_verification(),
        today=date(2026, 10, 24),
    )


# --- içerik dosyaları ---


def test_content_files_load_and_match_questions_and_sources() -> None:
    assert set(get_guides()) == {
        "miras_arac_devri",
        "mirascilik_belgesi",
        "pasaport",
        "kimlik_karti_yenileme",
        "ehliyet_yenileme",
        "yerlesim_yeri_belgesi",
    }


def test_every_quote_in_content_is_verified_in_committed_check_file() -> None:
    # İçerik değiştirildiğinde `python -m app.rehber kontrol` çalıştırılmadan geçmez.
    verification = get_verification()
    for guide in get_guides().values():
        for item in guide.evidence():
            assert verification.is_verified(item), f"{guide.islem}: {item.alinti[:60]}"


# Kullanıcıdan değer girmesini isteyen ifadeler (serbest metin, numara, adres yazdırma)
ENTRY_WORDS = ["yazın", "yazınız", "giriniz", "girin", "belirtiniz", "nedir?"]


def test_questions_are_choices_and_never_ask_for_personal_data() -> None:
    for guide in get_guides().values():
        process = get_process_type(guide.islem)
        slots = {s.key: s for s in process.slots}
        for question in guide.sorular:
            slot = slots[question.anahtar]
            # Serbest metin yok: her soru 2-6 hazır seçenekten oluşur
            assert 2 <= len(slot.options) <= 6, slot.key
            assert not any(w in slot.question.lower() for w in ENTRY_WORDS), slot.question
            for option in slot.options:
                assert not any(w in option.lower() for w in ENTRY_WORDS), option


def _guide(**overrides) -> Guide:
    data = {
        "islem": "miras_arac_devri",
        "ozet": "ö",
        "sorular": [{"anahtar": "mirasci_sayisi"}],
        "adimlar": [
            {
                "id": "a",
                "baslik": "b",
                "aciklama": "c",
                "kurum": "k",
                "dayanaklar": [
                    {"kaynak": "https://www.egm.gov.tr/trafik-tescil-hakkinda", "alinti": "x" * 20}
                ],
            }
        ],
    }
    data.update(overrides)
    return Guide.model_validate(data)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"sorular": [{"anahtar": "uydurma"}]}, "bilinmeyen soru"),
        (
            {"sorular": [{"anahtar": "mirasci_sayisi", "sor_eger": {"kisitlama": ["Var"]}}]},
            "sorulmayan soru",
        ),
        (
            {"sorular": [{"anahtar": "kisitlama", "sor_eger": {"kisitlama": ["Belki"]}}]},
            "geçersiz cevap",
        ),
    ],
)
def test_inconsistent_content_is_rejected(overrides: dict, message: str) -> None:
    with pytest.raises(GuideError, match=message):
        validate_guide(_guide(**overrides), MIRAS, SOURCES)


def test_quote_from_a_source_outside_the_process_list_is_rejected() -> None:
    guide = _guide()
    guide.adimlar[0].dayanaklar[0].kaynak = "https://www.nvi.gov.tr/baska-sayfa"
    with pytest.raises(GuideError, match="kaynak listesinde"):
        validate_guide(guide, MIRAS, SOURCES)


# --- akış ---


def test_conditions_and_or() -> None:
    assert matches(None, {})
    assert matches({"a": ["1"], "b": ["2"]}, {"a": "1", "b": "2"})
    assert not matches({"a": ["1"], "b": ["2"]}, {"a": "1"})
    assert matches({"a": [NOT_ASKED]}, {})
    assert matches([{"a": ["1"]}, {"b": ["2"]}], {"b": "2"})


def test_questions_are_skipped_when_not_relevant() -> None:
    guide = get_guides()["miras_arac_devri"]
    assert next_question(guide, MIRAS, {}).key == "mirascilik_belgesi"
    answers = {"mirascilik_belgesi": "Evet", "mirasci_sayisi": "Tek mirasçı"}
    # Tek mirasçıda "kimin adına" ve "birlikte mi başvurulacak" sorulmaz
    assert next_question(guide, MIRAS, answers).key == "kisitlama"
    answers |= {"kisitlama": "Yok", "beyanname_verildi": "Evet"}
    # Beyanname verildiyse beyanname süresi ve randevu soruları sorulmaz
    assert next_question(guide, MIRAS, answers) is None


def test_changing_an_earlier_answer_drops_answers_that_no_longer_apply() -> None:
    guide = get_guides()["miras_arac_devri"]
    answers = {
        "mirascilik_belgesi": "Evet",
        "mirasci_sayisi": "Tek mirasçı",
        "tescil_tercihi": "Mirasçılardan biri adına",
    }
    assert "tescil_tercihi" not in effective_answers(guide, MIRAS, answers)


def test_invalid_answer_is_ignored_and_question_asked_again() -> None:
    guide = get_guides()["miras_arac_devri"]
    answers = effective_answers(guide, MIRAS, {"mirascilik_belgesi": "Belki"})
    assert answers == {}
    assert next_question(guide, MIRAS, answers).key == "mirascilik_belgesi"


FULL = {
    "mirascilik_belgesi": "Hayır",
    "mirasci_sayisi": "Birden fazla mirasçı",
    "tescil_tercihi": "Mirasçılardan biri adına",
    "basvuru_sekli": "Evet, hepsi başvuracak",
    "kisitlama": "Yok",
    "beyanname_verildi": "Hayır",
    "vefat_ve_mirasci_yeri": "Vefat Türkiye'de, mirasçılar Türkiye'de",
    "buyuksehir": "Hayır",
}


def titles(result) -> list[str]:
    return [s.baslik for s in result.adimlar]


def test_roadmap_contains_only_steps_matching_answers() -> None:
    result = roadmap("miras_arac_devri", FULL)
    assert titles(result)[0] == "Mirasçılık belgesi (veraset ilamı) alın"
    assert "Noterde miras taksim sözleşmesi veya feragatname düzenletin" in titles(result)
    assert [s.sira for s in result.adimlar] == list(range(1, len(result.adimlar) + 1))
    assert all(ref.son_kontrol for s in result.adimlar for ref in s.kaynaklar)
    assert any("90 gün" in w for w in result.uyarilar)

    already_has = roadmap("miras_arac_devri", {**FULL, "mirascilik_belgesi": "Evet"})
    assert "Mirasçılık belgesi (veraset ilamı) alın" not in titles(already_has)
    all_heirs = roadmap("miras_arac_devri", {**FULL, "tescil_tercihi": "Tüm mirasçılar adına"})
    assert "Noterde miras taksim sözleşmesi veya feragatname düzenletin" not in titles(all_heirs)


def test_situations_without_sources_get_a_referral_note_not_invented_steps() -> None:
    result = roadmap("miras_arac_devri", {**FULL, "kisitlama": "Var"})
    assert any("trafik tescil kuruluşu ile görüşünüz" in w for w in result.uyarilar)
    assert result.guven == "orta"


def test_unapproved_content_is_flagged() -> None:
    result = roadmap("miras_arac_devri", FULL)
    assert UNAPPROVED_WARNING in result.uyarilar
    assert result.guven == "yuksek"  # onay eksikliği güveni düşürmez, ayrıca uyarılır


def test_step_is_hidden_when_its_quote_is_no_longer_found_in_the_source() -> None:
    verification = get_verification().model_copy(deep=True)
    guide = get_guides()["miras_arac_devri"]
    step = next(s for s in guide.adimlar if s.id == "sigorta_ve_muayene")
    verification.alintilar[step.dayanaklar[0].key] = False
    result = roadmap("miras_arac_devri", FULL, verification)
    assert step.baslik not in titles(result)
    assert any("1 adım" in w and "doğrulanamadığı" in w for w in result.uyarilar)


def test_changed_quote_text_needs_a_new_check() -> None:
    original = Evidence(kaynak="https://x", alinti="aynı kaynak metni burada")
    edited = Evidence(kaynak="https://x", alinti="değiştirilmiş kaynak metni")
    verification = Verification(
        kaynaklar={"https://x": SourceCheck(son_kontrol="2026-10-24", durum="ok")},
        alintilar={original.key: True},
    )
    assert verification.is_verified(original)
    assert not verification.is_verified(edited)


def test_no_verified_step_means_referral() -> None:
    assert roadmap("miras_arac_devri", FULL, Verification()) is None


def test_stale_sources_are_flagged() -> None:
    verification = get_verification().model_copy(deep=True)
    for check in verification.kaynaklar.values():
        check.son_kontrol = "2026-01-01"
    result = roadmap("miras_arac_devri", FULL, verification)
    assert any("30 günden uzun" in w for w in result.uyarilar)


def test_tax_return_deadline_depends_on_where_death_and_heirs_are() -> None:
    abroad = roadmap(
        "miras_arac_devri",
        {**FULL, "vefat_ve_mirasci_yeri": "Vefat yurt dışında, mirasçılar başka bir ülkede"},
    )
    assert "Beyanname süresi: ölüm tarihini takip eden 8 ay." in abroad.uyarilar
    assert "Beyanname süresi: ölüm tarihini takip eden 4 ay." not in abroad.uyarilar
    filed = roadmap("miras_arac_devri", {**FULL, "beyanname_verildi": "Evet"})
    assert "Veraset ve intikal vergisi beyannamesini verin" not in titles(filed)


def test_every_answer_path_of_every_guide_produces_a_roadmap() -> None:
    """Her rehberde olası tüm cevap yollarını dener; hiçbir yol boş yol haritası vermemeli."""
    for code, guide in get_guides().items():
        process = get_process_type(code)
        slots = {s.key: s for s in process.slots}
        paths: list[dict[str, str]] = [{}]
        finished = []
        while paths:
            answers = paths.pop()
            question = next_question(guide, process, answers)
            if question is None:
                finished.append(answers)
                continue
            paths.extend({**answers, question.key: o} for o in slots[question.key].options)
        assert finished, code
        for answers in finished:
            result = roadmap(code, answers)
            assert result is not None and result.adimlar, (code, answers)


def test_will_or_special_case_routes_to_court_without_asking_where() -> None:
    guide = get_guides()["mirascilik_belgesi"]
    answers = {"vasiyetname": "Var", "ozel_durum": "Hayır"}
    assert next_question(guide, BELGE, answers) is None
    old = {"vasiyetname": "Yok", "ozel_durum": "Hayır", "vefat_donemi": "04/04/1926'dan önce"}
    assert next_question(guide, BELGE, old) is None
    assert titles(roadmap("mirascilik_belgesi", old)) == ["Sulh hukuk mahkemesine başvurun"]
    result = roadmap("mirascilik_belgesi", answers)
    assert titles(result) == ["Sulh hukuk mahkemesine başvurun"]

    noter = roadmap(
        "mirascilik_belgesi",
        {
            "vasiyetname": "Yok",
            "ozel_durum": "Hayır",
            "vefat_donemi": "23/11/1990'dan sonra",
            "basvuru_yeri": "Noter",
            "temsilen_basvuru": "Mirasçı olarak kendim",
        },
    )
    assert titles(noter)[0] == "Bir noterliğe başvurun"


# --- uç nokta ---


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: Settings(
        internal_api_token="test-anahtari",  # noqa: S106
        _env_file=None,  # type: ignore[call-arg]
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_endpoint_requires_token(client) -> None:
    assert client.post("/v1/rehber", json={"islem": "miras_arac_devri"}).status_code == 401


def test_endpoint_walks_through_questions_then_returns_roadmap(client) -> None:
    body = client.post("/v1/rehber", json={"islem": "miras_arac_devri"}, headers=AUTH).json()
    assert body["durum"] == "soru"
    assert body["soru"]["anahtar"] == "mirascilik_belgesi"
    assert body["ilerleme"] == {"cevaplanan": 0, "toplam": 4}

    body = client.post(
        "/v1/rehber", json={"islem": "miras_arac_devri", "cevaplar": FULL}, headers=AUTH
    ).json()
    assert body["durum"] == "tamam"
    assert body["yol_haritasi"]["islem"] == "miras_arac_devri"
    assert body["cevaplar"] == FULL


def test_endpoint_unknown_process_is_404(client) -> None:
    response = client.post("/v1/rehber", json={"islem": "imei_kayit"}, headers=AUTH)
    assert response.status_code == 404


def test_endpoint_lists_available_guides(client) -> None:
    body = client.get("/v1/rehber", headers=AUTH).json()
    assert {g["islem"] for g in body} == set(get_guides())


def test_all_process_types_with_guides_exist() -> None:
    codes = {p.code for p in get_process_types()}
    assert set(get_guides()) <= codes
