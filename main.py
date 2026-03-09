import sys
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.jt_api.client import JTClient
from src.services.report_service import ReportService
from src.utils.exporter import export_to_csv

def main():
    try:
        with open("waybills.txt", "r") as f:
            waybills = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: No se encontró waybills.txt. Crea uno con una guía por línea.")
        return

    if not waybills:
        print("No hay guías para procesar en waybills.txt")
        return
    
    print(f"Iniciando procesamiento de {len(waybills)} guías...")
    
    try:
        with SessionLocal() as session:
            config_repo = ConfigRepository(session)
            config = config_repo.load_config()

            client = JTClient(config=config)
            tracking_repo = TrackingEventRepository(session)
            service = ReportService(client, tracking_repo)
        
            results = []
            for wb in waybills:
                print(f"{wb}", end=" ", flush=True)
                data = service.get_consolidated_data(wb)
                status_icon = "✅" if data.is_delivered else "🚚"
                print(f"-> {status_icon} {data.status} | P6: {data.arrival_punto6_time} | Entregado: {data.delivery_time}")
                results.append(data)

            print("-" * 30)
            export_to_csv(results, "reporte_consolidado.csv")
            entregados = sum(1 for r in results if r.is_delivered)
            print(f"Resumen: {entregados}/{len(results)} guías entregadas.")
        
    except Exception as e:
        print(f"Error fatal: {e}")

if __name__ == "__main__":
    main()
