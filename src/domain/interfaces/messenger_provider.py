from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from src.domain.messenger import MessengerProfile

class IMessengerProvider(ABC):
    @abstractmethod
    def search_messengers(self, name: str, network_code: Optional[str] = None) -> List[MessengerProfile]:
        """
        Busca mensajeros que coincidan con el nombre.
        """
        pass

    @abstractmethod
    def get_recent_waybill_no(self, account_code: str, network_code: Optional[str] = None) -> Optional[str]:
        """
        Obtiene el número de una guía reciente asignada a este mensajero.
        """
        pass

    @abstractmethod
    def get_contact_from_tracking(self, waybill_no: str, normalized_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Busca el contacto del mensajero en el historial de rastreo de una guía.
        Retorna (telefono, nombre) si se encuentra.
        """
        pass
