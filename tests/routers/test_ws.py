import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web_ui.routers.ws import router
from unittest.mock import patch, MagicMock

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_websocket_auth_failure():
    with patch("src.web_ui.security._is_authenticated_websocket", return_value=False):
        with pytest.raises(Exception): # TestClient raises on connection rejection
            with client.websocket_connect("/ws/process") as websocket:
                pass

@patch("src.web_ui.security._is_authenticated_websocket", return_value=True)
def test_websocket_connectivity(mock_auth):
    # Solo probamos que se pueda conectar y que el router esté bien configurado
    # El procesamiento real requiere mocks complejos de JTClient y ReportService
    with client.websocket_connect("/ws/notifications") as websocket:
        assert websocket is not None
