import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web_ui.routers.waybills import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_get_waybills_addresses_empty():
    # Test básico enviando lista vacía
    response = client.post("/api/waybills/addresses", json={"waybills": []})
    assert response.status_code == 200
    assert response.json() == {}

def test_get_waybills_phones_empty():
    response = client.post("/api/waybills/phones", json={"waybills": []})
    assert response.status_code == 200
    assert response.json() == {}

def test_get_waybills_details_empty():
    response = client.post("/api/waybills/details", json={"waybills": []})
    assert response.status_code == 200
    assert response.json() == {}

def test_get_waybills_timeline_missing():
    # Enviar un waybill vacío para probar validación
    response = client.get("/api/waybills/ /timeline")
    assert response.status_code == 400
    assert "reque" in response.json()["detail"].lower()
