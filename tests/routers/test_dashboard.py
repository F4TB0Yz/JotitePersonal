import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web_ui.routers.dashboard import router
from unittest.mock import patch, MagicMock

app = FastAPI()
app.include_router(router)
client = TestClient(app)

@patch("src.infrastructure.repositories.config_repository.ConfigRepository.get_cached")
@patch("src.jt_api.client.JTClient.search_messengers")
def test_global_search_success(mock_search, mock_config):
    mock_config.return_value = MagicMock()
    mock_search.return_value = {"code": 1, "data": {"records": []}}
    
    response = client.get("/api/search?q=test")
    assert response.status_code == 200
    assert "waybills" in response.json()

def test_global_search_short_query():
    response = client.get("/api/search?q=a")
    assert response.status_code == 200
    assert response.json()["waybills"] == []

@patch("src.services.kpi_service.KPIService.get_overview")
@patch("src.web_ui.routers.dashboard.SessionLocal")
def test_get_kpis_overview(mock_session_local, mock_get_overview):
    """
    Patches:
      - SessionLocal (used directly inside the endpoint closure)
      - KPIService.get_overview (to avoid real DB calls)

    The old test mocked a singleton `kpi_service.kpi_service` that no longer
    exists after the Clean Architecture / DI refactor.
    """
    mock_session_local.return_value.__enter__ = lambda s, *a: MagicMock()
    mock_session_local.return_value.__exit__ = lambda s, *a: None
    mock_get_overview.return_value = {"total": 100}

    response = client.get("/api/kpis/overview")
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 100
