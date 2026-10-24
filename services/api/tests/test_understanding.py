import json

import pytest
from rag_fixtures import PROCESS_TYPES

from app.llm import FakeProvider
from app.rag.understanding import UnderstandingError, understand


def reply(islem: str, cevaplar: dict[str, str] | None = None) -> str:
    return json.dumps(
        {
            "islem": islem,
            "gerekce": "Kısa gerekçe",
            "cevaplar": [{"anahtar": k, "deger": v} for k, v in (cevaplar or {}).items()],
        },
        ensure_ascii=False,
    )


def run(responses: list, text: str = "Babamdan kalan arabayı üzerime almak istiyorum", **kw):
    llm = FakeProvider(responses)
    return understand(text, llm=llm, process_types=PROCESS_TYPES, **kw), llm


def test_classifies_and_asks_missing_questions() -> None:
    result, llm = run([reply("miras_arac_devri")])
    assert result.status == "needs_clarification"
    assert result.process.code == "miras_arac_devri"
    assert [q.key for q in result.questions] == ["mirascilik_belgesi", "mirasci_sayisi"]
    schema = llm.calls[0]["schema"]
    assert schema["properties"]["islem"]["enum"] == ["miras_arac_devri", "pasaport", "kapsam_disi"]


def test_answers_found_in_text_are_not_asked_again() -> None:
    result, _ = run([reply("miras_arac_devri", {"mirasci_sayisi": "Tek mirasçı"})])
    assert result.answers == {"mirasci_sayisi": "Tek mirasçı"}
    assert [q.key for q in result.questions] == ["mirascilik_belgesi"]


def test_answers_outside_options_or_other_process_are_ignored() -> None:
    result, _ = run([reply("miras_arac_devri", {"mirasci_sayisi": "üç", "vasiyetname": "Var"})])
    assert result.answers == {}


def test_process_without_slots_is_ready_immediately() -> None:
    result, _ = run([reply("pasaport")], text="Pasaportumu yenilemek istiyorum")
    assert result.status == "ready" and result.questions == []


def test_out_of_scope() -> None:
    result, _ = run([reply("kapsam_disi")], text="Tapu devri nasıl yapılır?")
    assert result.status == "out_of_scope" and result.process is None


def test_second_round_with_known_process_skips_llm() -> None:
    result, llm = run(
        [],
        process_code="miras_arac_devri",
        answers={"mirascilik_belgesi": "Evet", "mirasci_sayisi": "Bilmiyorum"},
    )
    assert result.status == "ready"
    assert llm.calls == []


def test_unknown_process_code_is_rejected() -> None:
    with pytest.raises(ValueError):
        run([], process_code="uydurma")


def test_personal_data_is_masked_before_llm() -> None:
    _, llm = run([reply("miras_arac_devri")], text="34 ABC 123 plakalı aracı almak istiyorum")
    assert "34 ABC 123" not in llm.calls[0]["user"]


def test_invalid_twice_raises() -> None:
    with pytest.raises(UnderstandingError):
        run(["{}", "geçersiz"])
