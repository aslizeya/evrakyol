import json

import pytest
from rag_fixtures import CHUNKS, EGM, GOOD_STEPS, MIRAS_ARAC, TNB, FakeRetriever, roadmap_json, step

from app.llm import FakeProvider, LLMError
from app.rag.roadmap import RoadmapGenerationError, RoadmapService, fee_supported, quote_found


def build(responses: list, chunks=CHUNKS, answers=None, text="Babamdan kalan arabayı almak"):
    llm = FakeProvider(responses)
    retriever = FakeRetriever(chunks)
    outcome = RoadmapService(retriever, llm).build(text, MIRAS_ARAC, answers or {})
    return outcome, llm, retriever


# --- alıntı ve ücret doğrulama ---


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ("bir noterliğe gidiniz", True),
        ("BİR NOTERLİĞE   gidiniz.", True),  # büyük/küçük harf ve boşluk farkı önemsiz
        ("Aşağıdaki belgeler ... üç dakika içerisinde", True),  # üç noktayla bölünmüş alıntı
        ("üç dakika içerisinde ... Aşağıdaki belgeler", False),  # sıra bozuk
        ("bir avukata gidiniz", False),  # kaynakta yok
        ("noter", False),  # çok kısa: anlamlı dayanak sayılmaz
        ("MİRASÇILIK BELGESİ SİSTEM TARAFINDAN", True),  # Türkçe büyük harf (İ/I)
        ("Noterden Mirasçılık Belgesi Nasıl Alınır", True),  # başlık yolu da aranır
    ],
)
def test_quote_verification(quote: str, expected: bool) -> None:
    assert quote_found(quote, TNB) is expected


@pytest.mark.parametrize(
    ("fee", "expected"),
    [
        ("1.250,50 TL", True),
        ("1250,50 TL", True),  # binlik ayırıcı farkı önemsiz
        ("2.000 TL", False),
        ("1.250,50 TL + 90 TL", False),  # her sayı kaynakta olmalı
        ("Ücretsiz", False),  # kaynakta "ücretsiz" geçmiyor
    ],
)
def test_fee_verification(fee: str, expected: bool) -> None:
    assert fee_supported(fee, [EGM]) is expected


# --- yol haritası ---


def test_builds_roadmap_with_sources_from_database() -> None:
    outcome, llm, retriever = build([roadmap_json(GOOD_STEPS)])

    assert outcome.status == "ok"
    roadmap = outcome.roadmap
    assert [s.sira for s in roadmap.adimlar] == [1, 2]
    assert roadmap.islem == "miras_arac_devri"
    first = roadmap.adimlar[0].kaynaklar[0]
    assert first.url == TNB.url and first.baslik == "Mirasçılık Belgesi"
    assert first.son_kontrol == TNB.last_fetched_at.date().isoformat()
    assert roadmap.guven == "yuksek"
    assert outcome.source_ids == [1, 2]
    assert retriever.queries[0][1] == "miras_arac_devri"
    assert len(llm.calls) == 1


def test_step_with_unverifiable_quote_is_dropped_and_confidence_lowered() -> None:
    steps = [
        *GOOD_STEPS,
        step("Avukattan onay alın", [("K1", "avukat onayı zorunludur")]),
    ]
    outcome, _, _ = build([roadmap_json(steps)])

    titles = [s.baslik for s in outcome.roadmap.adimlar]
    assert "Avukattan onay alın" not in titles
    assert outcome.dropped_steps == 1
    assert outcome.roadmap.guven == "orta"
    assert any("1 adım resmi kaynakta doğrulanamadığı" in w for w in outcome.roadmap.uyarilar)


def test_step_citing_unknown_source_id_is_dropped() -> None:
    steps = [GOOD_STEPS[0], step("Uydurma", [("K9", "bir noterliğe gidiniz")])]
    outcome, _, _ = build([roadmap_json(steps)])
    assert [s.baslik for s in outcome.roadmap.adimlar] == [GOOD_STEPS[0]["baslik"]]


def test_quote_must_come_from_the_cited_source() -> None:
    # Alıntı K1'de var ama adım K2'ye dayandırılmış
    steps = [GOOD_STEPS[0], step("Yanlış kaynak", [("K2", "bir noterliğe gidiniz")])]
    outcome, _, _ = build([roadmap_json(steps)])
    assert outcome.dropped_steps == 1


def test_unsupported_fee_is_removed_supported_fee_kept() -> None:
    steps = [
        step("Noterden mirasçılık belgesi alın", [("K1", "bir noterliğe gidiniz")], "500 TL"),
        step("Tescil", [("K2", "Veraset ilamı veya mirasçılık belgesinin")], "1.250,50 TL"),
    ]
    outcome, _, _ = build([roadmap_json(steps)])
    first, second = outcome.roadmap.adimlar
    assert first.tahmini_ucret is None
    assert second.tahmini_ucret == "1.250,50 TL"
    assert any("ücret bilgisi kaynakta doğrulanamadığından" in w for w in outcome.roadmap.uyarilar)


def test_warnings_need_evidence_and_stale_sources_are_flagged() -> None:
    warnings = [
        {"metin": "Vefattan itibaren 90 gün içinde başvurun.",
         "dayanaklar": [{"kaynak": "K3", "alinti": "vefat tarihinden itibaren 90 gün içinde"}]},
        {"metin": "Uydurma uyarı", "dayanaklar": [{"kaynak": "K3", "alinti": "olmayan cümle"}]},
    ]  # fmt: skip
    steps = [*GOOD_STEPS, step("Süreyi kaçırmayın", [("K3", "90 gün içinde ilgili tescil")])]
    outcome, _, _ = build([roadmap_json(steps, warnings)])

    uyarilar = outcome.roadmap.uyarilar
    assert uyarilar[0] == "Vefattan itibaren 90 gün içinde başvurun."
    assert "Uydurma uyarı" not in uyarilar
    assert outcome.dropped_warnings == 1
    assert any("30 günden uzun süredir" in w and "Trafik Kanunu" in w for w in uyarilar)


def test_no_retrieved_sources_returns_referral_without_calling_llm() -> None:
    outcome, llm, _ = build([], chunks=[])
    assert outcome.status == "no_sources"
    assert outcome.referral == MIRAS_ARAC.referral
    assert llm.calls == []


def test_all_steps_unverifiable_returns_no_sources() -> None:
    outcome, _, _ = build([roadmap_json([step("Uydurma", [("K1", "hiç geçmeyen bir cümle")])])])
    assert outcome.status == "no_sources"
    assert outcome.dropped_steps == 1


def test_insufficient_sources_caps_confidence() -> None:
    outcome, _, _ = build([roadmap_json(GOOD_STEPS, yeterli_kaynak=False)])
    assert outcome.roadmap.guven == "orta"


def test_invalid_json_is_retried_once_then_succeeds() -> None:
    outcome, llm, _ = build(['{"eksik": true}', roadmap_json(GOOD_STEPS)])
    assert outcome.status == "ok"
    assert len(llm.calls) == 2
    assert "<not>" in llm.calls[1]["user"]


def test_two_invalid_responses_raise_instead_of_guessing() -> None:
    with pytest.raises(RoadmapGenerationError):
        build(["bu json değil", '{"adimlar": "yanlış"}'])


def test_llm_errors_propagate() -> None:
    with pytest.raises(LLMError):
        build([LLMError("refusal")])


def test_prompt_contains_masked_text_and_sources_as_data() -> None:
    _, llm, _ = build(
        [roadmap_json(GOOD_STEPS)],
        text="TC 12345678901, aracı almak istiyorum",
        answers={"mirascilik_belgesi": "Evet"},
    )
    user = llm.calls[0]["user"]
    assert "12345678901" not in user and "[TC_KIMLIK]" in user
    assert '<kaynak id="K1"' in user and '<kaynak id="K3"' in user
    assert "Mirasçılık belgesi alındı mı?" in user and ">Evet</cevap>" in user
    assert json.loads(json.dumps(llm.calls[0]["schema"]))["additionalProperties"] is False


def test_masked_text_is_returned_for_storage() -> None:
    outcome, _, _ = build([roadmap_json(GOOD_STEPS)], text="Telefonum 0532 123 45 67")
    assert outcome.masked_text == "Telefonum [TELEFON]"
