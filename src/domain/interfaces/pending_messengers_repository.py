from abc import ABC, abstractmethod
from typing import List, Dict, Any

class IPendingMessengersRepository(ABC):
    @abstractmethod
    def get_pending_messengers_data(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Consulta los mensajeros pendientes.
        Retorna una lista de diccionarios con la información cruda o procesada.
        Se espera que contenga 'name', 'pending_count' y 'phone' (si está disponible).
        """
        pass
