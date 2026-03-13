import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web_ui.routers.novedades import router
from unittest.mock import patch, MagicMock

app = FastAPI()
app.include_router(router)
client = TestClient(app)

@patch("src.services.novedades_service.novedades_service.get_all_novedades")
def test_get_novedades_success(mock_get_all):
    mock_get_all.return_value = [{"id": 1, "waybill": "WB123", "status": "OPEN"}]
    
    response = client.get("/api/novedades/")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["waybill"] == "WB123"

@patch("src.services.novedades_service.novedades_service.get_novedades_by_waybill")
def test_get_novedades_by_waybill(mock_get_by_wb):
    mock_get_by_wb.return_value = [{"id": 1, "waybill": "WB123"}]
    
    response = client.get("/api/novedades/?waybill=WB123")
    assert response.status_code == 200
    assert response.json()[0]["waybill"] == "WB123"
