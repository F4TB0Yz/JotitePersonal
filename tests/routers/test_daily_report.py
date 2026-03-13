import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web_ui.routers.daily_report import router
from src.infrastructure.database.deps import get_db
from unittest.mock import MagicMock

app = FastAPI()
app.include_router(router)
client = TestClient(app)

# Mock de la base de datos
mock_db = MagicMock()

def override_get_db():
    try:
        yield mock_db
    finally:
        pass

app.dependency_overrides[get_db] = override_get_db

def test_get_daily_report_entries_success():
    # Reiniciar el mock
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    
    mock_row = MagicMock()
    mock_row.id = 1
    mock_row.waybill_no = "WB123"
    mock_row.messenger_name = "Juan"
    mock_row.address = "Calle 1"
    mock_row.city = "Bogota"
    mock_row.status = "Delivered"
    mock_row.notes = "Ok"
    mock_row.report_date = "2023-10-01"
    
    mock_db.query().filter().order_by().all.return_value = [mock_row]
    
    response = client.get("/api/daily-report/entries?start_date=2023-10-01&end_date=2023-10-01")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["waybill_no"] == "WB123"

def test_get_daily_report_entries_invalid_date():
    response = client.get("/api/daily-report/entries?start_date=invalid&end_date=2023-10-01")
    assert response.status_code == 400
    assert "Fecha inválida" in response.json()["detail"]
