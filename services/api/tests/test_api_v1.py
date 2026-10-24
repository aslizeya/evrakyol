"""Uç nokta testleri: sahte LLM ve sahte arama ile (veritabanı gerekmez)."""

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from rag_fixtures import CHUNKS, GOOD_STEPS, FakeRetriever, roadmap_json

from app.api_v1 import get_retriever, llm_dependency
from app.config import Settings, get_settings
from app.llm import FakeProvider, LLMError
from app.main import app

AUTH = {"Authorization": "Bearer test-anahtari"}


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, dict]]:
    state: dict = {"llm": FakeProvider([]), "retriever": FakeRetriever(CHUNKS)}
    app.dependency_overrides[get_settings] = lambda: Settings(
        internal_api_token="test-anahtari",  # noqa: S106
        _env_file=None,  # type: ignore[call-arg]
    )
    app.dependency_overrides[llm_dependency] = lambda: state["llm"]
    app.dependency_overrides[get_retriever] = lambda: state["retriever"]
    yield TestClient(app), state
    app.dependency_overrides.clear()


def understanding(islem: str) -> str:
    return json.dumps({"islem": islem, "gerekce": "g", "cevaplar": []})


def test_endpoints_require_token(setup) -> None:
    client, _ = setup
    assert client.post("/v1/understand", json={"text": "merhaba"}).status_code == 401
    assert client.post("/v1/roadmap", json={"text": "x", "process_code": "p"}).status_code == 401


def test_understand_returns_questions_from_config(setup) -> None:
    client, state = setup
    state["llm"] = FakeProvider([understanding("miras_arac_devri")])
    body = client.post(
        "/v1/understand", json={"text": "Babamdan kalan arabayı almak istiyorum"}, headers=AUTH
    ).json()
    assert body["status"] == "needs_clarification"
    assert body["process_name"] == "Miras yoluyla araç devri"
    assert 1 <= len(body["questions"]) <= 3
    assert body["questions"][0]["options"]


def test_understand_out_of_scope_lists_supported_processes(setup) -> None:
    client, state = setup
    state["llm"] = FakeProvider([understanding("kapsam_disi")])
    body = client.post("/v1/understand", json={"text": "Tapu devri"}, headers=AUTH).json()
    assert body["status"] == "out_of_scope"
    assert "Pasaport" in body["message"]


def test_roadmap_ok(setup) -> None:
    client, state = setup
    state["llm"] = FakeProvider([roadmap_json(GOOD_STEPS)])
    response = client.post(
        "/v1/roadmap",
        json={"text": "Babamdan kalan arabayı almak", "process_code": "miras_arac_devri"},
        headers=AUTH,
    )
    body = response.json()
    assert response.status_code == 200, body
    assert body["status"] == "ok"
    assert set(body["roadmap"]) == {"islem", "ozet", "adimlar", "uyarilar", "guven"}
    assert set(body["roadmap"]["adimlar"][0]) == {
        "sira", "baslik", "aciklama", "gerekli_evraklar", "kurum", "tahmini_ucret", "kaynaklar",
    }  # fmt: skip
    assert set(body["roadmap"]["adimlar"][0]["kaynaklar"][0]) == {"baslik", "url", "son_kontrol"}


def test_roadmap_no_sources_message(setup) -> None:
    client, state = setup
    state["retriever"] = FakeRetriever([])
    body = client.post(
        "/v1/roadmap", json={"text": "aracı almak", "process_code": "pasaport"}, headers=AUTH
    ).json()
    assert body["status"] == "no_sources"
    assert "Nüfus ve Vatandaşlık" in body["message"]
    assert body["roadmap"] is None


def test_roadmap_generation_failure_is_an_error_not_a_guess(setup) -> None:
    client, state = setup
    state["llm"] = FakeProvider(["{}", "{}"])
    response = client.post(
        "/v1/roadmap",
        json={"text": "aracı almak", "process_code": "miras_arac_devri"},
        headers=AUTH,
    )
    assert response.status_code == 502
    assert "Yanlış bilgi vermemek için" in response.json()["detail"]


def test_llm_unavailable_maps_to_503(setup) -> None:
    client, state = setup
    state["llm"] = FakeProvider([LLMError("budget_exceeded")])
    response = client.post("/v1/understand", json={"text": "aracı almak"}, headers=AUTH)
    assert response.status_code == 503
    assert "Günlük kullanım sınırına" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "x" * 2001},
        {"text": "ab"},
        {"text": "aracı almak", "answers": {f"k{i}": "v" for i in range(11)}},
    ],
)
def test_input_validation(setup, payload) -> None:
    client, _ = setup
    assert client.post("/v1/understand", json=payload, headers=AUTH).status_code == 422


def test_unknown_process_code(setup) -> None:
    client, _ = setup
    response = client.post(
        "/v1/roadmap", json={"text": "aracı almak", "process_code": "uydurma"}, headers=AUTH
    )
    assert response.status_code == 422


def test_missing_llm_configuration_is_503_not_500(setup, monkeypatch) -> None:
    client, _ = setup
    del app.dependency_overrides[llm_dependency]

    def not_configured():
        raise LLMError("not_configured", "ANTHROPIC_API_KEY tanımlı değil")

    monkeypatch.setattr("app.api_v1.get_llm", not_configured)
    response = client.post("/v1/understand", json={"text": "aracı almak"}, headers=AUTH)
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" not in response.text  # yapılandırma ayrıntısı kullanıcıya sızmaz
