import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web_ui.routers.auth import router
from src.infrastructure.database.deps import get_db
from unittest.mock import MagicMock, patch

app = FastAPI()
app.include_router(router)
client = TestClient(app)

mock_db = MagicMock()

def override_get_db():
    yield mock_db

app.dependency_overrides[get_db] = override_get_db

def test_serve_login():
    with patch("src.web_ui.security._is_authenticated_request", return_value=False):
        response = client.get("/login")
        assert response.status_code == 200
        # HTML content check
        assert b"html" in response.content.lower()

def test_login_invalid_credentials():
    with patch("src.web_ui.security._resolve_dashboard_password", return_value="secret"):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
        assert response.status_code == 401

@patch("src.web_ui.security._resolve_dashboard_password", return_value="secret")
@patch("src.web_ui.security._create_session_token", return_value="fake_token")
def test_login_success(mock_token, mock_pass):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert "jt_session" in response.cookies

def test_logout():
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert "jt_session" not in response.cookies or response.cookies.get("jt_session") == ""

def test_update_token_success():
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    response = client.post("/api/config/token", json={"authToken": "new_token"})
    assert response.status_code == 200
    assert "success" in response.json()["status"]
    mock_db.add.assert_called()
    mock_db.commit.assert_called()
