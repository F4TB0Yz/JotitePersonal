import logging
from typing import List, Dict, Any
from src.domain.messenger import MessengerContact
from src.domain.exceptions import NoDataFoundError, ReportGenerationError
from src.domain.interfaces.pending_messengers_repository import IPendingMessengersRepository
from src.domain.interfaces.pdf_generator_provider import PdfGeneratorProvider

logger = logging.getLogger(__name__)

class GeneratePendingMessengersReportUseCase:
    """
    Caso de Uso para generar un reporte PDF de los mensajeros pendientes.
    Mapea los datos del repositorio a MessengerContact y genera el PDF.
    """

    def __init__(self, repo: IPendingMessengersRepository, pdf_provider: PdfGeneratorProvider):
        self.repo = repo
        self.pdf_provider = pdf_provider

    def execute(self, criteria: Dict[str, Any]) -> bytes:
        """
        Ejecuta la lógica para generar el reporte de mensajeros pendientes.
        
        :param criteria: Criterios de filtrado (ej. red, rango de fechas).
        :return: Bytes del reporte PDF.
        :raises NoDataFoundError: Si no hay datos para el reporte.
        :raises ReportGenerationError: Si ocurre un error en la generación del PDF.
        """
        # 1. Consultar el repositorio de datos
        raw_data = self.repo.get_pending_messengers_data(criteria)

        # 2. Validar que la lista no esté vacía
        if not raw_data:
            raise NoDataFoundError("No hay mensajeros pendientes para generar el reporte.")

        # 3. Mapear datos a MessengerContact
        report_cities_for = criteria.get("reportCityMessengers", [])
        
        messengers: List[MessengerContact] = []
        for item in raw_data:
            name = item.get("name", "Desconocido")
            # Incluir la ciudad solo si el mensajero fue marcado en la selección
            city = item.get("city") if name in report_cities_for else None
            
            messengers.append(MessengerContact(
                name=name,
                phone=item.get("phone") or "N/A",
                pending_count=item.get("pending_count", 0),
                city=city
            ))

        # 4. Generar el PDF
        try:
            return self.pdf_provider.generate_pending_messengers_report(messengers)
        except Exception as e:
            # Captura errores de la librería PDF y los envuelve en la excepción de dominio
            logger.exception("Error crítico generando PDF de mensajeros")
            raise ReportGenerationError(f"Error al generar el PDF: {str(e)}")
