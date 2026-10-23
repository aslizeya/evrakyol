from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_session
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def _override_session(session: MagicMock) -> None:
    app.dependency_overrides[get_session] = lambda: session


def test_health_ok(client: TestClient) -> None:
    _override_session(MagicMock())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_unavailable_database_without_leaking_details(client: TestClient) -> None:
    session = MagicMock()
    session.execute.side_effect = OperationalError(
        "SELECT 1", {}, Exception("password=gizli host=db")
    )
    _override_session(session)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
    assert "gizli" not in response.text
