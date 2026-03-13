import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web_ui.routers.returns import router
from unittest.mock import patch, MagicMock

app = FastAPI()
app.include_router(router)
client = TestClient(app)

@patch("src.web_ui.routers.returns._build_returns_service")
def test_get_return_snapshots_success(mock_build_service):
    # Mocking the service method
    mock_service = MagicMock()
    mock_service.list_snapshots.return_value = [{"waybillNo": "RET123", "status": 1}]
    mock_build_service.return_value = mock_service
    
    response = client.get("/api/returns/snapshots?status=1")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["waybillNo"] == "RET123"

def test_get_return_snapshots_invalid_status():
    response = client.get("/api/returns/snapshots?status=5")
    assert response.status_code == 400
    assert "status debe ser" in response.json()["detail"]
