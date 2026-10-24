from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_session
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _with_token(token: str | None) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        internal_api_token=token,
        _env_file=None,  # type: ignore[call-arg]
    )


def test_admin_closed_when_token_not_configured(client: TestClient) -> None:
    _with_token(None)
    assert client.get("/admin/sources").status_code == 503


@pytest.mark.parametrize("header", [None, "Bearer yanlis", "Basic dogru-anahtar", "dogru-anahtar"])
def test_admin_rejects_missing_or_wrong_token(client: TestClient, header: str | None) -> None:
    _with_token("dogru-anahtar")
    headers = {"Authorization": header} if header else {}
    assert client.get("/admin/sources", headers=headers).status_code == 401
