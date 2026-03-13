import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web_ui.routers.settlements import router
from unittest.mock import patch, MagicMock

app = FastAPI()
app.include_router(router)
client = TestClient(app)

@patch("src.services.settlement_service.SettlementService.get_rate")
@patch("src.infrastructure.repositories.config_repository.ConfigRepository.get_cached")
def test_get_messenger_rate_success(mock_config, mock_get_rate):
    # Mocking the service method
    mock_get_rate.return_value = {"accountCode": "JP001", "rate": 1500.0}
    mock_config.return_value = MagicMock()
    
    response = client.get("/api/settlements/rate?account_code=JP001")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["accountCode"] == "JP001"
    assert response.json()["data"]["rate"] == 1500.0

@patch("src.services.settlement_service.SettlementService.get_rate")
@patch("src.infrastructure.repositories.config_repository.ConfigRepository.get_cached")
def test_get_messenger_rate_not_found(mock_config, mock_get_rate):
    # Mocking the service method to return None or similar
    mock_get_rate.return_value = None
    mock_config.return_value = MagicMock()
    
    response = client.get("/api/settlements/rate?account_code=UNKNOWN")
    assert response.status_code == 200 # As per implementation, it returns success: True, data: None if script doesn't raise
    assert response.json()["success"] is True
    assert response.json()["data"] is None
