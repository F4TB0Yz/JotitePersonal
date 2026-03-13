from datetime import datetime, timedelta

from src.infrastructure.database.connection import initialize_database, SessionLocal
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.jt_api.client import JTClient
from src.models.waybill import (
    TrackingEvent, ConsolidatedReportRow
)
from src.domain.exceptions import APIError

class ReportService:
    def __init__(self, client: JTClient, tracking_repo: TrackingEventRepository = None):
        self.client = client
        initialize_database()
        self.tracking_repo = tracking_repo if tracking_repo is not None else TrackingEventRepository(SessionLocal())

    @staticmethod
    def _is_signed_event(event: "TrackingEvent") -> bool:
        """Detecta evento de entrega/firma sin importar idioma del status.
        code=100 es el código universal de J&T para 'Paquete firmado'.
        """
        if event.code == 100:
            return True
        status = (event.status or "").lower()
        type_name = (event.type_name or "").lower()
        return (
            "firmado" in status
            or "paquete firmado" in type_name
            or "firmado" in type_name
            # Código chino para firmado por si acaso
            or "签收" in (event.status or "")
        )

    @staticmethod
    def _parse_tracking_events(tracking_json: dict) -> list[TrackingEvent]:
        tracking_data = tracking_json.get("data", [])
        events = []
        if tracking_data:
            for item in tracking_data[0].get("details", []):
                events.append(TrackingEvent(
                    time=item.get("scanTime") or "",
                    type_name=item.get("scanTypeName") or "Desconocido",
                    network_name=item.get("scanNetworkName") or "N/A",
                    scan_network_id=str(item.get("scanNetworkId") or ""),
                    staff_name=item.get("staffName") or item.get("scanByName"),
                    staff_contact=item.get("staffContact"),
                    status=item.get("status") or "",
                    content=item.get("waybillTrackingContent") or "",
                    code=item.get("code"),
                ))
        return events

    def get_timeline(self, waybill_no: str, max_age_minutes: int = 30) -> list[TrackingEvent]:
        cached_events, last_fetch = self.tracking_repo.get_events_for_waybill(waybill_no)
        freshness_cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        if cached_events and last_fetch and last_fetch >= freshness_cutoff:
            return cached_events

        try:
            tracking_json = self.client.get_tracking_list(waybill_no)
        except APIError:
            return cached_events

        events = self._parse_tracking_events(tracking_json)
        self.tracking_repo.save_events(waybill_no, events)
        return events

    def get_consolidated_data(self, waybill_no: str) -> ConsolidatedReportRow:
        # 1. Obtener detalles básicos
        try:
            order_json = self.client.get_order_detail(waybill_no)
            details = order_json.get("data", {}).get("details", {})
        except APIError:
            details = {}
        
        # 2. Obtener rastreo (Timeline)
        try:
            tracking_json = self.client.get_tracking_list(waybill_no)
            events = self._parse_tracking_events(tracking_json)
            self.tracking_repo.save_events(waybill_no, events)
        except APIError:
            events, _ = self.tracking_repo.get_events_for_waybill(waybill_no)

        # 3. Obtener excepciones
        try:
            abnormal_json = self.client.get_abnormal_list(waybill_no)
            abnormal_records = abnormal_json.get("data", {}).get("records", [])
            exceptions = [rec.get("abnormalPieceName") for rec in abnormal_records if rec.get("abnormalPieceName")]
            last_exception_remark = abnormal_records[0].get("remark") if abnormal_records else ""
        except APIError:
            exceptions = []
            last_exception_remark = ""

        # Consolidar (Tomar el evento más reciente)
        last_event = events[0] if events else None
        # is_delivered es True si CUALQUIER evento es de firma, no solo el primero
        is_delivered = any(self._is_signed_event(e) for e in events)

        # Buscar fechas específicas
        arrival_punto6 = "N/A"
        delivery_date = "N/A"
        signing_event = None

        for event in events:
            # Arribo a Punto 6 (Descarga TR1/2 en Cund-Punto6)
            if "Cund-Punto6" in event.network_name and "Descarga" in event.type_name:
                arrival_punto6 = event.time
            # Fecha de entrega (Firmado) — guardar el evento de firma
            if self._is_signed_event(event) and signing_event is None:
                delivery_date = event.time
                signing_event = event

        # El status mostrado debe reflejar la firma si existe
        display_status = (
            signing_event.type_name if signing_event
            else (last_event.status or last_event.type_name) if last_event
            else "Desconocido"
        )

        return ConsolidatedReportRow(
            waybill_no=waybill_no,
            status=display_status,
            order_source=details.get("orderSourceName", "N/A"),
            sender=details.get("senderName", "N/A"),
            receiver=details.get("receiverName", "N/A"),
            city=details.get("receiverCityName", "N/A"),
            weight=details.get("packageChargeWeight", 0.0),
            last_event_time=last_event.time if last_event else "N/A",
            last_network=last_event.network_name if last_event else "N/A",
            last_staff=last_event.staff_name if last_event else "N/A",
            staff_contact=last_event.staff_contact if last_event else "N/A",
            is_delivered=is_delivered,
            arrival_punto6_time=arrival_punto6,
            delivery_time=delivery_date,
            address=details.get("receiverDetailedAddress", "N/A"),
            exceptions=", ".join(set(exceptions)),
            last_remark=last_exception_remark
        )
