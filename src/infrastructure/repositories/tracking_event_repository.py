from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from typing import List, Tuple, Optional
from src.infrastructure.database.models import TrackingEventORM
from src.models.waybill import TrackingEvent
from src.domain.enums.waybill_enums import are_networks_equivalent

_SQLITE_CHUNK = 900  # below SQLite's variable limit of 999


class TrackingEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Write ─────────────────────────────────────────────────────────────────

    def save_events(self, waybill_no: str, events: List[TrackingEvent]) -> None:
        """
        Bulk-upsert a list of tracking events for a single waybill.

        Strategy: deduplicate in-memory by (time, type_name), then issue a
        single ``INSERT OR REPLACE`` statement per unique event (SQLite dialect).
        ``INSERT OR REPLACE`` triggers on the table's UNIQUE constraint
        ``(waybill_no, time, type_name)`` and replaces the row atomically,
        avoiding the previous SELECT-per-event N+1 pattern.

        Args:
            waybill_no: The waybill identifier these events belong to.
            events:     Ordered list of ``TrackingEvent`` domain objects.
        """
        if not events:
            return

        now = datetime.utcnow()
        seen: set[tuple[str, str]] = set()
        rows: list[dict] = []

        for event in events:
            event_time = event.time or ""
            event_type = event.type_name or "Desconocido"
            identity = (event_time, event_type)
            if identity in seen:
                continue
            seen.add(identity)
            rows.append({
                "waybill_no": waybill_no,
                "time": event_time,
                "type_name": event_type,
                "network_name": event.network_name,
                "scan_network_id": event.scan_network_id,
                "staff_name": event.staff_name,
                "staff_contact": event.staff_contact or "",
                "status": event.status,
                "content": event.content,
                "event_code": event.code,
                "fetched_at": now,
            })

        if not rows:
            return

        # Single bulk statement — SQLite INSERT OR REPLACE honours the
        # UNIQUE(waybill_no, time, type_name) constraint and updates in place.
        self.session.connection().execute(
            text(
                "INSERT OR REPLACE INTO tracking_events "
                "(waybill_no, time, type_name, network_name, scan_network_id, "
                " staff_name, staff_contact, status, content, event_code, fetched_at) "
                "VALUES "
                "(:waybill_no, :time, :type_name, :network_name, :scan_network_id, "
                " :staff_name, :staff_contact, :status, :content, :event_code, :fetched_at)"
            ),
            rows,
        )
        self.session.commit()

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_departed_waybills(
        self,
        waybill_nos: list[str],
        current_network_id: str | None = None,
    ) -> set[str]:
        """
        Given a list of pending waybills, returns those whose local tracking
        history indicates they have already left the current node
        (``current_network_id``).

        A waybill is considered *departed* when its most recent physical scan:
        1. Has a terminal event code (1=dispatch, 5=delivery, 7=return, 80=signed).
        2. Was recorded at a network different from ``current_network_id``.
        3. Contains a terminal status name as a fallback when code is absent.
        4. Is a "Carga y expedición" event originating from this same network.

        Args:
            waybill_nos:        List of canonical waybill numbers to evaluate.
            current_network_id: The node's network identifier for comparison.

        Returns:
            Set of waybill numbers confirmed as departed.
        """
        if not waybill_nos:
            return set()

        departed: set[str] = set()

        for offset in range(0, len(waybill_nos), _SQLITE_CHUNK):
            chunk = waybill_nos[offset: offset + _SQLITE_CHUNK]
            departed |= self._evaluate_departed_chunk(chunk, current_network_id)

        return departed

    def _evaluate_departed_chunk(
        self, chunk: list[str], current_network_id: str | None
    ) -> set[str]:
        subq = (
            self.session.query(
                TrackingEventORM.waybill_no,
                TrackingEventORM.event_code,
                TrackingEventORM.scan_network_id,
                TrackingEventORM.type_name,
                func.row_number()
                .over(
                    partition_by=TrackingEventORM.waybill_no,
                    order_by=TrackingEventORM.time.desc(),
                )
                .label("rn"),
            )
            .filter(TrackingEventORM.waybill_no.in_(chunk))
            .subquery()
        )
        rows = (
            self.session.query(
                subq.c.waybill_no,
                subq.c.event_code,
                subq.c.scan_network_id,
                subq.c.type_name,
            )
            .filter(subq.c.rn == 1)
            .all()
        )
        return {
            wb for wb, e_code, scan_net_id, t_name in rows
            if self._is_departed(e_code, scan_net_id, t_name, current_network_id)
        }

    @staticmethod
    def _is_departed(
        e_code: int | None,
        scan_net_id: str | None,
        t_name: str | None,
        current_network_id: str | None,
    ) -> bool:
        """Pure predicate: returns True when the latest scan indicates departure."""
        if e_code in (1, 5, 7, 80):
            return True
        if current_network_id and scan_net_id:
            if not are_networks_equivalent(scan_net_id, current_network_id):
                return True
        if t_name and any(s in t_name for s in ("Entregado", "Devuelto", "Firmado")):
            return True
        if t_name == "Carga y expedición" and (
            are_networks_equivalent(scan_net_id, current_network_id)
            or str(scan_net_id) == "1009"
        ):
            return True
        return False

    def get_events_for_waybill(
        self, waybill_no: str
    ) -> Tuple[List[TrackingEvent], Optional[datetime]]:
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
                scan_network_id=row.scan_network_id or "",
                staff_name=row.staff_name,
                staff_contact=row.staff_contact,
                status=row.status or "",
                content=row.content or "",
                code=row.event_code,
            )
            for row in rows
        ]
        return events, last_fetch

    def get_latest_delivery_events(self, waybill_nos: List[str]) -> dict[str, str]:
        """
        Returns the most recent delivery staff name for each waybill, filtered
        to scan events of type "Escaneo de entrega" or event code 94.

        Args:
            waybill_nos: List of canonical waybill numbers.

        Returns:
            Dict mapping waybill_no → staff_name for waybills with known courier.
        """
        if not waybill_nos:
            return {}

        staff_map: dict[str, str] = {}
        chunks = [
            waybill_nos[i: i + _SQLITE_CHUNK]
            for i in range(0, len(waybill_nos), _SQLITE_CHUNK)
        ]
        for chunk in chunks:
            staff_map |= self._latest_delivery_chunk(chunk)
        return staff_map

    def _latest_delivery_chunk(self, chunk: list[str]) -> dict[str, str]:
        subq = (
            self.session.query(
                TrackingEventORM.waybill_no,
                TrackingEventORM.staff_name,
                func.row_number()
                .over(
                    partition_by=TrackingEventORM.waybill_no,
                    order_by=TrackingEventORM.time.desc(),
                )
                .label("rn"),
            )
            .filter(
                and_(
                    TrackingEventORM.waybill_no.in_(chunk),
                    or_(
                        TrackingEventORM.type_name == "Escaneo de entrega",
                        TrackingEventORM.event_code == 94,
                    ),
                )
            )
            .subquery()
        )
        rows = (
            self.session.query(subq.c.waybill_no, subq.c.staff_name)
            .filter(subq.c.rn == 1)
            .all()
        )
        return {wb: name for wb, name in rows if name}
