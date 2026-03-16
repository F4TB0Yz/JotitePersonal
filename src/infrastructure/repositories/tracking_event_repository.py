from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import insert, func, and_
from typing import List, Tuple, Optional
from src.infrastructure.database.models import TrackingEventORM
from src.models.waybill import TrackingEvent
from src.domain.enums.waybill_enums import are_networks_equivalent

_SQLITE_CHUNK = 900  # por debajo del límite de variables de SQLite (999)

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
                exists.scan_network_id = event.scan_network_id
                exists.staff_name = event.staff_name
                exists.staff_contact = event.staff_contact
                exists.status = event.status
                exists.content = event.content
                exists.event_code = event.code
                exists.fetched_at = now
            else:
                connection.execute(
                    insert(TrackingEventORM).values(
                        waybill_no=waybill_no,
                        time=event_time,
                        type_name=event_type,
                        network_name=event.network_name,
                        scan_network_id=event.scan_network_id,
                        staff_name=event.staff_name,
                        staff_contact=event.staff_contact,
                        status=event.status,
                        content=event.content,
                        event_code=event.code,
                        fetched_at=now,
                    )
                )

        self.session.commit()

    @staticmethod
    def get_departed_waybills(
        session: Session,
        waybill_nos: list[str],
        current_network_id: str | None = None,
    ) -> set[str]:
        """
Dada una lista de guías pendientes, devuelve aquellas que según su historial
        ya salieron de la sucursal actual (current_network_id).
        
        Se considera que el paquete salió:
        1. Su último estado físico (por fecha) tiene code = 1 (despacho/Carga y expedición).
        2. O su último estado físico (por fecha) se registró en una red diferente (scanNetworkId != current_network_id).
        """
        if not waybill_nos:
            return set()

        # Usar set para mayor velocidad de búsqueda
        departed_wbs: set[str] = set()

        for offset in range(0, len(waybill_nos), _SQLITE_CHUNK):
            chunk = waybill_nos[offset : offset + _SQLITE_CHUNK]

            # Subconsulta súper optimizada: saca solo el PRIMER registro (más reciente) de cada guía
            # Filtramos estados de excepción (como los 4, 6, 8 u otros donde e_code puede ser nulo o diferente)
            # Para que rn=1 corresponda al último evento que marca su posición (despachado, inventariado, etc)
            subq = (
                session.query(
                    TrackingEventORM.waybill_no,
                    TrackingEventORM.event_code,
                    TrackingEventORM.scan_network_id,
                    TrackingEventORM.type_name,
                    func.row_number().over(
                        partition_by=TrackingEventORM.waybill_no,
                        order_by=TrackingEventORM.time.desc(),
                    ).label("rn"),
                )
                .filter(TrackingEventORM.waybill_no.in_(chunk))
                .subquery()
            )

            # Extraemos el escaneo `rn=1` (el más reciente NO excepcional)
            rows = session.query(
                subq.c.waybill_no, 
                subq.c.event_code, 
                subq.c.scan_network_id,
                subq.c.type_name
            ).filter(subq.c.rn == 1).all()

            for wb, e_code, scan_net_id, t_name in rows:                
                # Lógica agresiva: 
                # 1. Códigos terminales (Despacho, Entrega, Devolución, Firmado)
                if e_code in (1, 5, 7, 80):
                    departed_wbs.add(wb)
                    continue

                # 2. Si hay red de escaneo y NO coincide con la actual, se considera fuera.
                # Ignoramos escaneos sin red (ID vacío o None) para no filtrar por error.
                if current_network_id and scan_net_id:
                    if not are_networks_equivalent(scan_net_id, current_network_id):
                        departed_wbs.add(wb)
                        continue
                
                # 3. Fallback por nombre de estado si el código es nulo
                if t_name and ("Entregado" in t_name or "Devuelto" in t_name or "Firmado" in t_name):
                    departed_wbs.add(wb)
                    continue
                
                # 4. Filtro específico: Carga y expedición en esta red significa que YA SALIÓ.
                if t_name == "Carga y expedición" and (are_networks_equivalent(scan_net_id, current_network_id) or str(scan_net_id) == "1009"):
                    departed_wbs.add(wb)

        return departed_wbs

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
