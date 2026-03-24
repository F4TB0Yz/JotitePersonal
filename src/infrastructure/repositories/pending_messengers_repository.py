from typing import List, Dict, Any
from src.domain.interfaces.pending_messengers_repository import IPendingMessengersRepository
from src.services.waybill_network_service import WaybillNetworkService, WaybillFilterCriteria
from src.services.get_messenger_contact_use_case import GetMessengerContactUseCase
import logging
from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)

class PendingMessengersRepositoryImpl(IPendingMessengersRepository):
    """
    Implementación de IPendingMessengersRepository.
    Usa WaybillNetworkService para obtener la matriz y GetMessengerContactUseCase para resolver teléfonos.
    """

    def __init__(self, network_service: WaybillNetworkService, contact_use_case: GetMessengerContactUseCase):
        self.network_service = network_service
        self.contact_use_case = contact_use_case

    def get_pending_messengers_data(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Consulta los mensajeros pendientes y enriquece con su teléfono.
        """
        try:
            # Parsear el diccionario a WaybillFilterCriteria
            net_criteria = WaybillFilterCriteria(**criteria)
        except Exception as e:
            logger.error(f"Error al parsear criterios: {e}")
            return []

        # Crear un BackgroundTasks vacío para no interferir con la lógica de fondo
        bg_tasks = BackgroundTasks()
        
        # Obtener la matriz (que agrupa por staff)
        matrix = self.network_service.get_network_waybills(net_criteria, bg_tasks)

        result = []
        for row in matrix.rows:
            name = row.staff
            count = row.total
            phone = "N/A"

            # Excluir 'Sin enrutar' ya que no es un mensajero real
            if name and name.strip() and name.lower() != "sin enrutar":
                try:
                    contact = self.contact_use_case.execute(
                        name=name,
                        network_code=net_criteria.network_code
                    )
                    if contact.phone:
                        phone = contact.phone
                except Exception as e:
                    # Logueamos la advertencia pero continuamos para no fallar el reporte entero
                    logger.warning(f"No se pudo resolver el teléfono para '{name}': {e}")

            result.append({
                "name": name,
                "pending_count": count,
                "phone": phone,
                "city": row.assigned_city
            })

        return result
