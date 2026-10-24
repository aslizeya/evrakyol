"""Yönetici kaynak uç noktaları (gerçek Postgres)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app import admin
from app.config import Settings, get_settings
from app.db import get_session
from app.main import app

pytestmark = pytest.mark.db

AUTH = {"Authorization": "Bearer test-anahtari"}


@pytest.fixture
def client(db_sessionmaker: sessionmaker[Session], monkeypatch) -> Iterator[TestClient]:
    def session() -> Iterator[Session]:
        with db_sessionmaker() as s:
            yield s

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_settings] = lambda: Settings(
        internal_api_token="test-anahtari",  # noqa: S106
        _env_file=None,  # type: ignore[call-arg]
    )
    queued: list[tuple[int, bool]] = []
    monkeypatch.setattr(admin, "_reindex", lambda sid, force: queued.append((sid, force)))
    c = TestClient(app)
    c.queued = queued  # type: ignore[attr-defined]
    yield c
    app.dependency_overrides.clear()


NEW_SOURCE = {
    "url": "https://www.nvi.gov.tr/pasaport",
    "title": "Pasaport",
    "process_codes": ["pasaport"],
}


def test_create_list_update_source(client: TestClient) -> None:
    created = client.post("/admin/sources", json=NEW_SOURCE, headers=AUTH)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["institution"] == "Nüfus ve Vatandaşlık İşleri Genel Müdürlüğü"
    assert body["chunk_count"] == 0 and body["last_status"] is None

    listed = client.get("/admin/sources", headers=AUTH).json()
    assert [s["url"] for s in listed] == [NEW_SOURCE["url"]]

    updated = client.patch(f"/admin/sources/{body['id']}", json={"active": False}, headers=AUTH)
    assert updated.json()["active"] is False


def test_rejects_source_outside_allowlist(client: TestClient) -> None:
    response = client.post(
        "/admin/sources",
        json={**NEW_SOURCE, "url": "https://ornek-blog.com/pasaport"},
        headers=AUTH,
    )
    assert response.status_code == 422


def test_rejects_unknown_process_code(client: TestClient) -> None:
    response = client.post(
        "/admin/sources", json={**NEW_SOURCE, "process_codes": ["uydurma"]}, headers=AUTH
    )
    assert response.status_code == 422


def test_duplicate_url_conflicts(client: TestClient) -> None:
    client.post("/admin/sources", json=NEW_SOURCE, headers=AUTH)
    assert client.post("/admin/sources", json=NEW_SOURCE, headers=AUTH).status_code == 409


def test_reindex_is_queued_in_background(client: TestClient) -> None:
    source_id = client.post("/admin/sources", json=NEW_SOURCE, headers=AUTH).json()["id"]
    response = client.post(f"/admin/sources/{source_id}/reindex", headers=AUTH)
    assert response.status_code == 202
    assert client.queued == [(source_id, True)]  # type: ignore[attr-defined]
    assert client.post("/admin/sources/999999/reindex", headers=AUTH).status_code == 404
