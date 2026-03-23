from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from src.domain.messenger import MessengerProfile, JTClientIntegrationException
from src.domain.interfaces.messenger_provider import IMessengerProvider
from src.jt_api.client import JTClient
from src.infrastructure.repositories.config_repository import ConfigRepository

class JTMessengerProvider(IMessengerProvider):
    """
    Proveedor de mensajeros que consulta los servicios de JTClient.
    Enmascara cualquier error de integración en excepciones de dominio.
    """

    def _get_client(self) -> JTClient:
        try:
            config = ConfigRepository.get_cached()
            return JTClient(config=config)
        except Exception as e:
            raise JTClientIntegrationException(f"Error al inicializar JTClient: {str(e)}")

    def search_messengers(self, name: str, network_code: Optional[str] = None) -> List[MessengerProfile]:
        try:
            client = self._get_client()
            # La API necesita un text para buscar
            response = client.search_messengers(name, network_id=network_code)
            return self._extract_profiles(response)
        except Exception as e:
            raise JTClientIntegrationException(f"Error buscando mensajeros en la API: {str(e)}")

    def get_recent_waybill_no(self, account_code: str, network_code: Optional[str] = None) -> Optional[str]:
        try:
            client = self._get_client()
            today_dt = datetime.now()
            end_str = today_dt.strftime("%Y-%m-%d 23:59:59")
            start_str = (today_dt - timedelta(days=3)).strftime("%Y-%m-%d 00:00:00")
            
            net_code = network_code or "1025006"
            wb_resp = client.get_messenger_waybills_detail(account_code, net_code, start_str, end_str, current=1, size=1)
            
            return self._extract_waybill_no(wb_resp)
        except Exception as e:
            raise JTClientIntegrationException(f"Error obteniendo guías recientes: {str(e)}")

    def get_contact_from_tracking(self, waybill_no: str, normalized_name: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            client = self._get_client()
            tracking = client.get_tracking_list(waybill_no)
            return self._extract_contact_from_tracking(tracking, normalized_name)
        except Exception as e:
            raise JTClientIntegrationException(f"Error consultando rastreo: {str(e)}")

    def _extract_profiles(self, response: dict) -> List[MessengerProfile]:
        # Evita .get().get() inseguro
        data = response.get("data") if response else {}
        records = data.get("records") if isinstance(data, dict) else data
        
        if records and not isinstance(records, list):
            records = [records]
            
        if not records:
            return []
            
        return [MessengerProfile(**r) for r in records if isinstance(r, dict)]

    def _extract_waybill_no(self, wb_resp: dict) -> Optional[str]:
        if not wb_resp or wb_resp.get("code") != 1:
            return None
        
        wb_records = wb_resp.get("data", {}).get("records", [])
        if wb_records and isinstance(wb_records, list) and len(wb_records) > 0:
            return wb_records[0].get("waybillNo")
        return None

    def _extract_contact_from_tracking(self, tracking: dict, normalized_name: str) -> Tuple[Optional[str], Optional[str]]:
        data = tracking.get("data") or []
        prioritized = None
        fallback = None
        
        for entry in data:
            for detail in entry.get("details", []):
                contact = detail.get("staffContact")
                if not contact:
                    continue
                staff_name = (detail.get("staffName") or "").strip()
                if staff_name and staff_name.lower() == normalized_name:
                    prioritized = (contact, staff_name)
                    break
                if not fallback:
                    fallback = (contact, staff_name)
            if prioritized:
                break
                
        chosen = prioritized or fallback
        if chosen:
            return chosen
        return None, None
