import json
from src.jt_api.client import JTClient
from src.services.report_service import ReportService
import json

from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository

def test_full_report():
    try:
        with SessionLocal() as session:
            config_repo = ConfigRepository(session)
            config = config_repo.load_config()
            tracking_repo = TrackingEventRepository(session)

        client = JTClient(config=config)
        service = ReportService(client, tracking_repo)
        waybill = "JTC000036927414" # Guía de ejemplo (esperamos Firmado)
        
        print(f"--- Probando Consolidación de Datos ({waybill}) ---")
        data = service.get_consolidated_data(waybill)
        
        print(f"Guía: {data.waybill_no}")
        print(f"Estado: {data.status}")
        print(f"¿Entregado (Firmado)?: {'SÍ' if data.is_delivered else 'NO'}")
        print(f"Último Mensajero: {data.last_staff} ({data.staff_contact})")
        print(f"Excepciones: {data.exceptions if data.exceptions else 'Ninguna'}")
        
    except FileNotFoundError:
        print("Error: No se encontró config.json.")
    except Exception as e:
        print(f"Error en la prueba: {e}")

if __name__ == "__main__":
    test_full_report()
