import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web_ui.routers.messengers import router
from unittest.mock import patch, MagicMock

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_search_messengers_empty_query():
    # q=a is less than 2 chars, should return []
    response = client.get("/api/messengers/search?q=a")
    assert response.status_code == 200
    assert response.json() == []

@patch("src.jt_api.client.JTClient.search_messengers")
@patch("src.infrastructure.repositories.config_repository.ConfigRepository.get_cached")
def test_search_messengers_success(mock_config, mock_search):
    # Mocking JTClient response
    mock_search.return_value = {
        "code": 1,
        "data": {
            "records": [{"accountName": "Juan Pérez", "accountCode": "JP001"}]
        }
    }
    mock_config.return_value = MagicMock()
    
    response = client.get("/api/messengers/search?q=Juan")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["accountName"] == "Juan Pérez"
