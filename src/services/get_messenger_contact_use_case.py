from typing import Optional
from src.domain.messenger import MessengerContact, MessengerNotFoundException, MessengerProfile
from src.domain.interfaces.messenger_provider import IMessengerProvider

class GetMessengerContactUseCase:
    """
    Caso de Uso para obtener el contacto de un mensajero.
    Orquesta la estrategia de búsqueda y fallback para encontrar el teléfono.
    """

    def __init__(self, provider: IMessengerProvider):
        self.provider = provider

    def execute(self, name: str, network_code: Optional[str] = "1009", waybill: Optional[str] = None) -> MessengerContact:
        if not name or not name.strip():
            raise ValueError("Nombre requerido")

        normalized = name.strip().lower()
        records = self.provider.search_messengers(name.strip(), network_code)
        
        best_match = self._find_best_match(records, normalized)
        phone_value = best_match.get_phone() if best_match else None
        account_code = best_match.accountCode if best_match else None

        # Estrategia de Fallback 1: Buscar guía de los últimos 3 días
        final_waybill = waybill
        if not phone_value and not final_waybill and account_code:
            net_code = best_match.customerNetworkCode if best_match else network_code
            final_waybill = self.provider.get_recent_waybill_no(account_code, net_code)

        # Estrategia de Fallback 2: Buscar contacto en el historial de rastreo
        tracking_phone = None
        tracking_name = None
        if not phone_value and final_waybill and final_waybill.strip():
            tracking_phone, tracking_name = self.provider.get_contact_from_tracking(
                final_waybill.strip(), normalized
            )

        final_phone = phone_value or tracking_phone
        final_name = self._resolve_final_name(name, best_match, tracking_name)
        network_name = best_match.customerNetworkName if best_match else None

        if not final_phone and not best_match:
            raise MessengerNotFoundException("Mensajero no encontrado")

        return MessengerContact(
            name=final_name,
            accountCode=account_code,
            networkName=network_name,
            phone=final_phone
        )

    def _find_best_match(self, records: list[MessengerProfile], normalized_name: str) -> Optional[MessengerProfile]:
        if not records:
            return None
        # Intenta coincidencia exacta
        for record in records:
            if record.accountName and record.accountName.strip().lower() == normalized_name:
                return record
        # Retorna el primero si no hay exacta
        return records[0]

    def _resolve_final_name(self, original_name: str, best_match: Optional[MessengerProfile], tracking_name: Optional[str]) -> str:
        if tracking_name:
            return tracking_name
        if best_match and best_match.accountName:
            return best_match.accountName
        return original_name.strip()
