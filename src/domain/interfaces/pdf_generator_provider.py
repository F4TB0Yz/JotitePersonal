from abc import ABC, abstractmethod
from src.domain.messenger import MessengerContact

class PdfGeneratorProvider(ABC):
    @abstractmethod
    def generate_pending_messengers_report(self, messengers: list[MessengerContact]) -> bytes:
        """
        Genera un reporte PDF con la lista de mensajeros pendientes.
        """
        pass
