from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import insert
from typing import List, Tuple, Optional
from src.infrastructure.database.models import TrackingEventORM
from src.models.waybill import TrackingEvent

class TrackingEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_events(self, waybill_no: str, events: List[TrackingEvent]) -> None:
        if not events:
            return

        now = datetime.utcnow()
        seen_identity = set()

        # Usar la conexión directa para inserts (saltar flush conflicts)
        connection = self.session.connection()

        for event in events:
            event_time = event.time or ""
            event_type = event.type_name or "Desconocido"
            identity = (event_time, event_type)
            if identity in seen_identity:
                continue
            seen_identity.add(identity)

            exists = (
                self.session.query(TrackingEventORM)
                .filter(
                    TrackingEventORM.waybill_no == waybill_no,
                    TrackingEventORM.time == event_time,
                    TrackingEventORM.type_name == event_type,
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
            else:
                connection.execute(
                    insert(TrackingEventORM).values(
                        waybill_no=waybill_no,
                        time=event_time,
                        type_name=event_type,
                        network_name=event.network_name,
                        staff_name=event.staff_name,
                        staff_contact=event.staff_contact,
                        status=event.status,
                        content=event.content,
                        fetched_at=now,
                    )
                )

        self.session.commit()

    def get_events_for_waybill(self, waybill_no: str) -> Tuple[List[TrackingEvent], Optional[datetime]]:
        rows = (
            self.session.query(TrackingEventORM)
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
