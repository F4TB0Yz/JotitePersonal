import json
from src.jt_api.client import JTClient
from src.services.report_service import ReportService
import json

def test_full_report():
    try:
        client = JTClient()
        service = ReportService(client)
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
