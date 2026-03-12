import json
from datetime import datetime
from typing import Any

from src.infrastructure.database.connection import SessionLocal, initialize_database
from src.infrastructure.database.models import ReturnApplicationSnapshotORM
from src.jt_api.client import JTClient


class ReturnsService:
    def __init__(self, client: JTClient, apply_network_id: int = 1009):
        self.client = client
        self.apply_network_id = int(apply_network_id)
        initialize_database()

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _normalize_record(record: dict[str, Any], source_status: int, synced_at: str) -> dict[str, Any]:
        return {
            "waybill_no": record.get("waybillNo") or "",
            "source_status": source_status,
            "status_name": record.get("statusName") or "",
            "apply_time": record.get("applyTime") or "",
            "examine_time": record.get("examineTime") or "",
            "apply_network_id": record.get("applyNetworkId"),
            "apply_network_name": record.get("applyNetworkName") or "",
            "apply_staff_code": record.get("applyStaffCode") or "",
            "apply_staff_name": record.get("applyStaffName") or "",
            "examine_staff_name": record.get("examineStaffName") or "",
            "reback_transfer_reason": record.get("rebackTransferReason") or "",
            "print_flag": record.get("printFlag"),
            "synced_at": synced_at,
            "raw": record,
        }

    def fetch_applications(
        self,
        status: int,
        apply_time_from: str,
        apply_time_to: str,
        current: int = 1,
        size: int = 20,
        save_snapshot: bool = True,
    ) -> dict[str, Any]:
        source_status = self._to_int(status)
        if source_status not in (1, 2):
            raise ValueError("status debe ser 1 (En revisión) o 2 (Aprobada)")

        response = self.client.get_return_applications_page(
            apply_network_id=self.apply_network_id,
            apply_time_from=apply_time_from,
            apply_time_to=apply_time_to,
            status=source_status,
            current=max(1, self._to_int(current, 1)),
            size=min(max(1, self._to_int(size, 20)), 100),
        )

        if response.get("code") != 1:
            raise ValueError(response.get("msg") or "Error consultando devoluciones")

        data = response.get("data") or {}
        records = data.get("records") or []
        synced_at = datetime.now().isoformat()

        normalized = [self._normalize_record(item, source_status, synced_at) for item in records]

        inserted_count = 0
        if save_snapshot and normalized:
            inserted_count = self._save_snapshots(normalized)

        return {
            "records": normalized,
            "total": self._to_int(data.get("total"), len(normalized)),
            "size": self._to_int(data.get("size"), size),
            "current": self._to_int(data.get("current"), current),
            "pages": self._to_int(data.get("pages"), 0),
            "status": source_status,
            "synced_at": synced_at,
            "snapshots_inserted": inserted_count,
        }

    def _save_snapshots(self, records: list[dict[str, Any]]) -> int:
        inserted = 0
        with SessionLocal() as session:
            for item in records:
                waybill_no = (item.get("waybill_no") or "").strip().upper()
                source_status = self._to_int(item.get("source_status"))
                apply_time = item.get("apply_time") or ""
                if not waybill_no:
                    continue

                exists = (
                    session.query(ReturnApplicationSnapshotORM)
                    .filter(ReturnApplicationSnapshotORM.waybill_no == waybill_no)
                    .filter(ReturnApplicationSnapshotORM.source_status == source_status)
                    .filter(ReturnApplicationSnapshotORM.apply_time == apply_time)
                    .first()
                )
                if exists:
                    continue

                row = ReturnApplicationSnapshotORM(
                    waybill_no=waybill_no,
                    source_status=source_status,
                    status_name=item.get("status_name") or "",
                    apply_time=apply_time,
                    examine_time=item.get("examine_time") or None,
                    apply_network_id=self._to_int(item.get("apply_network_id"), 0) or None,
                    apply_network_name=item.get("apply_network_name") or None,
                    apply_staff_code=item.get("apply_staff_code") or None,
                    apply_staff_name=item.get("apply_staff_name") or None,
                    examine_staff_name=item.get("examine_staff_name") or None,
                    reback_transfer_reason=item.get("reback_transfer_reason") or None,
                    print_flag=self._to_int(item.get("print_flag"), 0),
                    raw_json=json.dumps(item.get("raw") or {}, ensure_ascii=False),
                )
                session.add(row)
                inserted += 1

            session.commit()

        return inserted

    @staticmethod
    def _serialize_snapshot(row: ReturnApplicationSnapshotORM) -> dict[str, Any]:
        try:
            raw = json.loads(row.raw_json) if row.raw_json else {}
        except Exception:
            raw = {}
        return {
            "id": row.id,
            "waybill_no": row.waybill_no,
            "source_status": row.source_status,
            "status_name": row.status_name,
            "apply_time": row.apply_time,
            "examine_time": row.examine_time,
            "apply_network_id": row.apply_network_id,
            "apply_network_name": row.apply_network_name,
            "apply_staff_code": row.apply_staff_code,
            "apply_staff_name": row.apply_staff_name,
            "examine_staff_name": row.examine_staff_name,
            "reback_transfer_reason": row.reback_transfer_reason,
            "print_flag": row.print_flag,
            "synced_at": row.synced_at.isoformat() if row.synced_at else None,
            "raw": raw,
        }

    def list_snapshots(
        self,
        status: int | None = None,
        waybill_no: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        safe_limit = min(max(1, self._to_int(limit, 100)), 200)
        safe_offset = max(0, self._to_int(offset, 0))

        with SessionLocal() as session:
            query = session.query(ReturnApplicationSnapshotORM)

            if status in (1, 2):
                query = query.filter(ReturnApplicationSnapshotORM.source_status == int(status))

            if waybill_no:
                query = query.filter(ReturnApplicationSnapshotORM.waybill_no == waybill_no.strip().upper())

            if date_from:
                query = query.filter(ReturnApplicationSnapshotORM.apply_time >= date_from)
            if date_to:
                query = query.filter(ReturnApplicationSnapshotORM.apply_time <= date_to)

            total = query.count()
            rows = (
                query.order_by(ReturnApplicationSnapshotORM.synced_at.desc(), ReturnApplicationSnapshotORM.id.desc())
                .offset(safe_offset)
                .limit(safe_limit)
                .all()
            )

            return {
                "records": [self._serialize_snapshot(row) for row in rows],
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
            }

    def sync_statuses(
        self,
        apply_time_from: str,
        apply_time_to: str,
        statuses: list[int] | tuple[int, ...] = (1, 2),
        size: int = 50,
        max_pages: int = 20,
    ) -> dict[str, Any]:
        statuses_to_sync = [s for s in statuses if s in (1, 2)] or [1, 2]
        safe_size = min(max(1, self._to_int(size, 50)), 100)
        safe_max_pages = min(max(1, self._to_int(max_pages, 20)), 100)

        result: dict[str, Any] = {
            "from": apply_time_from,
            "to": apply_time_to,
            "statuses": statuses_to_sync,
            "pages_processed": 0,
            "records_seen": 0,
            "snapshots_inserted": 0,
        }

        for status in statuses_to_sync:
            for page in range(1, safe_max_pages + 1):
                data = self.fetch_applications(
                    status=status,
                    apply_time_from=apply_time_from,
                    apply_time_to=apply_time_to,
                    current=page,
                    size=safe_size,
                    save_snapshot=True,
                )
                records = data.get("records") or []
                result["pages_processed"] += 1
                result["records_seen"] += len(records)
                result["snapshots_inserted"] += self._to_int(data.get("snapshots_inserted"), 0)

                pages = self._to_int(data.get("pages"), 0)
                if not records:
                    break
                if pages and page >= pages:
                    break
                if len(records) < safe_size:
                    break

        return result
