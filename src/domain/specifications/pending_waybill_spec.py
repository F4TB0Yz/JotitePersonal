from typing import List, Optional
import logging
from src.models.waybill import TrackingEvent
from src.domain.enums.waybill_enums import WaybillStatusEnum, are_networks_equivalent, is_bogota_network, is_centro_network

logger = logging.getLogger(__name__)

class ExcludeRulesComposite:
    """
    Especificación de Dominio para determinar si un paquete debe ser EXCLUIDO 
    de la lista de pendientes basado en su historial de eventos.
    
    Patrón Specification (Clean Architecture).
    """
    def __init__(self, target_network: str):
        self.target_network = target_network
        self.rules = [
            self.TerminalStatusRule(),
            self.CargaExpedicionRule(target_network),
            self.DifferentNetworkRule(target_network),
            self.BogotaCentroRule(target_network)
        ]

    def should_exclude(self, events: List[TrackingEvent]) -> bool:
        """Retorna True si el paquete debe ser excluido."""
        if not events:
            return False
            
        for rule in self.rules:
            if rule.is_satisfied_by(events):
                logger.debug(f"Paquete excluido por regla: {rule.__class__.__name__}")
                return True
        return False

    class TerminalStatusRule:
        """Excluye si el paquete ya fue entregado o devuelto."""
        def is_satisfied_by(self, events: List[TrackingEvent]) -> bool:
            terminals = [
                WaybillStatusEnum.ENTREGADO.value, 
                WaybillStatusEnum.DEVUELTO.value, 
                WaybillStatusEnum.FIRMADO.value,
                "Paquete firmado"
            ]
            # Si ALGÚN evento en el historial tiene un estado terminal, se excluye
            return any(
                any(t in (e.type_name or "") or t in (e.status or "") for t in terminals) or
                (e.code == 100 or e.code in (170, 172))
                for e in events
            )

    class CargaExpedicionRule:
        """Excluye si el paquete salió de la red objetivo hacia otro nodo."""
        def __init__(self, target_network: str):
            self.target_network = target_network
            
        def is_satisfied_by(self, events: List[TrackingEvent]) -> bool:
            return any(
                (e.type_name == "Carga y expedición" or e.code == 1) and 
                (e.network_name == self.target_network or are_networks_equivalent(e.scan_network_id, self.target_network))
                for e in events
            )

    class DifferentNetworkRule:
        """Excluye si el último escaneo físico ocurrió en una red fuera de jurisdicción."""
        def __init__(self, target_network: str):
            self.target_network = target_network
            
        def is_satisfied_by(self, events: List[TrackingEvent]) -> bool:
            if not events: 
                return False
            # Asumimos que events[0] es el más reciente (sorted desc)
            last_event = events[0]
            
            # Si el nombre coincide exactamente o el ID es equivalente, es la misma red
            is_same_net = (
                (last_event.network_name == self.target_network) or
                are_networks_equivalent(last_event.scan_network_id, self.target_network)
            )
            
            return not is_same_net

    class BogotaCentroRule:
        """Regla especial para nodos Metropolitanos (Bogotá/Centro)."""
        def __init__(self, target_network: str):
            # Resolvemos si la red objetivo es Bogotá
            self.current_is_bogota = is_bogota_network(target_network)
            
        def is_satisfied_by(self, events: List[TrackingEvent]) -> bool:
            if not events:
                return False
            last_event = events[0]
            r_net_name = last_event.network_name or ""
            r_net_id = last_event.scan_network_id or ""
            
            # Verificamos si el escaneo actual es en Bogotá/Centro
            scan_is_bogota_zone = (
                is_bogota_network(r_net_name) or is_centro_network(r_net_name) or
                is_bogota_network(r_net_id) or is_centro_network(r_net_id)
            )
            
            # Si el escaneo es en Bogotá/Centro pero mi red NO lo es, excluyo.
            return scan_is_bogota_zone and not self.current_is_bogota
