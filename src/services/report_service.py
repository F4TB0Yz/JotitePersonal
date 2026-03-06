from datetime import datetime, timedelta

from src.infrastructure.database.connection import SessionLocal, initialize_database
from src.infrastructure.database.models import TrackingEventORM
from src.jt_api.client import JTClient
from src.models.waybill import (
    JTWaybillDetail, TrackingEvent, AbnormalScan, ConsolidatedReportRow
)

class ReportService:
    def __init__(self, client: JTClient):
        self.client = client
        initialize_database()

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
                    staff_name=item.get("staffName") or item.get("scanByName"),
                    staff_contact=item.get("staffContact"),
                    status=item.get("status") or "",
                    content=item.get("waybillTrackingContent") or ""
                ))
        return events

    def _save_tracking_events(self, waybill_no: str, events: list[TrackingEvent]) -> None:
        if not events:
            return
        now = datetime.utcnow()
        with SessionLocal() as session:
            for event in events:
                exists = (
                    session.query(TrackingEventORM)
                    .filter(
                        TrackingEventORM.waybill_no == waybill_no,
                        TrackingEventORM.time == (event.time or ""),
                        TrackingEventORM.type_name == (event.type_name or "Desconocido"),
                    )
                    .first()
                )
                if exists:
                    exists.network_name = event.network_name
                    exists.staff_name = event.staff_name
                    exists.staff_contact = event.staff_contact
                    exists.status = event.status
                    exists.content = event.content
                    exists.fetched_at = now
                    continue

                session.add(TrackingEventORM(
                    waybill_no=waybill_no,
                    time=event.time or "",
                    type_name=event.type_name or "Desconocido",
                    network_name=event.network_name,
                    staff_name=event.staff_name,
                    staff_contact=event.staff_contact,
                    status=event.status,
                    content=event.content,
                    fetched_at=now,
                ))
            session.commit()

    def get_cached_tracking_events(self, waybill_no: str) -> tuple[list[TrackingEvent], datetime | None]:
        with SessionLocal() as session:
            rows = (
                session.query(TrackingEventORM)
                .filter(TrackingEventORM.waybill_no == waybill_no)
                .order_by(TrackingEventORM.time.desc(), TrackingEventORM.id.desc())
                .all()
            )

            if not rows:
                return [], None

            last_fetch = rows[0].fetched_at
            events = [
                TrackingEvent(
                    time=row.time,
                    type_name=row.type_name,
                    network_name=row.network_name or "N/A",
                    staff_name=row.staff_name,
                    staff_contact=row.staff_contact,
                    status=row.status or "",
                    content=row.content or "",
                )
                for row in rows
            ]
            return events, last_fetch

    def get_timeline(self, waybill_no: str, max_age_minutes: int = 30) -> list[TrackingEvent]:
        cached_events, last_fetch = self.get_cached_tracking_events(waybill_no)
        freshness_cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        if cached_events and last_fetch and last_fetch >= freshness_cutoff:
            return cached_events

        tracking_json = self.client.get_tracking_list(waybill_no)
        events = self._parse_tracking_events(tracking_json)
        self._save_tracking_events(waybill_no, events)
        return events

    def get_consolidated_data(self, waybill_no: str) -> ConsolidatedReportRow:
        # 1. Obtener detalles básicos
        order_json = self.client.get_order_detail(waybill_no)
        details = order_json.get("data", {}).get("details", {})
        
        # 2. Obtener rastreo (Timeline)
        tracking_json = self.client.get_tracking_list(waybill_no)
        events = self._parse_tracking_events(tracking_json)
        self._save_tracking_events(waybill_no, events)

        # 3. Obtener excepciones
        abnormal_json = self.client.get_abnormal_list(waybill_no)
        abnormal_records = abnormal_json.get("data", {}).get("records", [])
        exceptions = [rec.get("abnormalPieceName") for rec in abnormal_records if rec.get("abnormalPieceName")]
        last_exception_remark = abnormal_records[0].get("remark") if abnormal_records else ""

        # Consolidar (Tomar el evento más reciente)
        last_event = events[0] if events else None
        is_delivered = last_event.status == "Firmado" if last_event else False
        
        # Buscar fechas específicas
        arrival_punto6 = "N/A"
        delivery_date = "N/A"
        
        for event in events:
            # Arribo a Punto 6 (Descarga TR1/2 en Cund-Punto6)
            if "Cund-Punto6" in event.network_name and "Descarga" in event.type_name:
                arrival_punto6 = event.time
            # Fecha de entrega (Firmado)
            if event.status == "Firmado":
                delivery_date = event.time

        return ConsolidatedReportRow(
            waybill_no=waybill_no,
            status=last_event.status if last_event else "Desconocido",
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
