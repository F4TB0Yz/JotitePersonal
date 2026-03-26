import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.infrastructure.repositories.config_repository import ConfigRepository
from src.jt_api.client import JTClient
from src.infrastructure.database.connection import SessionLocal

def main():
    db = SessionLocal()
    try:
        config = ConfigRepository.get_cached()
        client = JTClient(config=config)
        
        waybill = "JTC000033848870"
        print(f"Fetching tracking for {waybill}...")
        tracking = client.get_tracking_list(waybill)
        
        print("\n--- RAW TRACKING ---")
        print(json.dumps(tracking, indent=2, ensure_ascii=False))
        
        from src.services.report_service import ReportService
        from src.infrastructure.repositories.returns_repository import ReturnsRepository
        from src.infrastructure.repositories.novedades_repository import NovedadesRepository
        
        service = ReportService(client, ReturnsRepository(db), NovedadesRepository(db))
        events = service._parse_tracking_events(tracking)
        
        print("\n--- PARSED EVENTS ---")
        for i, e in enumerate(events):
            is_signed = service._is_signed_event(e)
            print(f"[{i}] {e.time} | Code: {e.code} | Type: {e.type_name} | Status: {e.status} | Content: {e.content} | Signed: {is_signed}")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
