from datetime import datetime, timedelta

from src.infrastructure.database.connection import initialize_database, SessionLocal
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.jt_api.client import JTClient
from src.models.waybill import (
    TrackingEvent, ConsolidatedReportRow
)
from src.domain.exceptions import APIError

class ReportService:
    def __init__(self, client: JTClient, returns_repo, novedades_repo, tracking_repo=None):
        self.client = client
        self.returns_repo = returns_repo
        self.novedades_repo = novedades_repo
        self.tracking_repo = tracking_repo if tracking_repo is not None else TrackingEventRepository(returns_repo.session)

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
        from src.domain.exceptions import DomainException
        try:
            return self._run_consolidated_data(waybill_no)
        except DomainException:
            raise
        except Exception as exc:
            raise DomainException(f"Error consolidando datos para la guía {waybill_no}: {exc}")

    def _run_consolidated_data(self, waybill_no: str) -> ConsolidatedReportRow:
        # 1. Obtener detalles básicos
        try:
            order_json = self.client.get_order_detail(waybill_no)
            details = order_json.get("data", {}).get("details", {}) or {}
        except APIError:
            details = {}
        
        # 2. Obtener rastreo (Timeline)
        try:
            tracking_json = self.client.get_tracking_list(waybill_no)
            events = self._parse_tracking_events(tracking_json)
            self.tracking_repo.save_events(waybill_no, events)
        except APIError:
            events, _ = self.tracking_repo.get_events_for_waybill(waybill_no)

        # 3. Obtener excepciones API
        try:
            abnormal_json = self.client.get_abnormal_list(waybill_no)
            abnormal_records = abnormal_json.get("data", {}).get("records", []) or []
            exceptions = [rec.get("abnormalPieceName") for rec in abnormal_records if rec.get("abnormalPieceName")]
            last_exception_remark = abnormal_records[0].get("remark") if abnormal_records else ""
        except APIError:
            exceptions = []
            last_exception_remark = ""

        # 4. Cruzar con Repositorios Locales (Novedades y Devoluciones)
        local_return_reasons = []
        try:
            return_data = self.returns_repo.list_snapshots(waybill_no=waybill_no)
            local_returns = return_data.get("records", [])
            local_return_reasons = [r.get("reback_transfer_reason") for r in local_returns if r.get("reback_transfer_reason")]
        except Exception:
            pass

        local_novedades_desc = []
        try:
            local_novedades = self.novedades_repo.get_by_waybill(waybill_no)
            local_novedades_desc = [n.description for n in local_novedades if n.description]
        except Exception:
            pass

        all_exceptions = list(set(exceptions + local_return_reasons + local_novedades_desc))

        # Consolidar (Tomar el evento más reciente)
        last_event = events[0] if events else None
        is_delivered = any(self._is_signed_event(e) for e in events)

        # Buscar fechas específicas
        arrival_punto6 = "N/A"
        delivery_date = "N/A"
        signing_event = None

        for event in events:
            if "Cund-Punto6" in (event.network_name or "") and "Descarga" in (event.type_name or ""):
                arrival_punto6 = event.time
            if self._is_signed_event(event) and signing_event is None:
                delivery_date = event.time
                signing_event = event

        display_status = (
            signing_event.type_name if signing_event
            else (last_event.status or last_event.type_name) if last_event
            else "Desconocido"
        )

        return ConsolidatedReportRow(
            waybill_no=waybill_no,
            status=display_status or "Desconocido",
            order_source=details.get("orderSourceName") or "N/A",
            sender=details.get("senderName") or "N/A",
            receiver=details.get("receiverName") or "N/A",
            city=details.get("receiverCityName") or "N/A",
            weight=float(details.get("packageChargeWeight") or 0.0),
            last_event_time=last_event.time if last_event else "N/A",
            last_network=last_event.network_name if last_event else "N/A",
            last_staff=last_event.staff_name if last_event else "N/A",
            staff_contact=last_event.staff_contact if last_event else "N/A",
            is_delivered=is_delivered,
            arrival_punto6_time=arrival_punto6 or "N/A",
            delivery_time=delivery_date or "N/A",
            address=details.get("receiverDetailedAddress") or "N/A",
            exceptions=", ".join(all_exceptions),
            last_remark=last_exception_remark or ""
        )
