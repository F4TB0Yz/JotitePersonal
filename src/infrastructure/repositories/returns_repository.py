import json
from datetime import datetime
from typing import Any, Optional
from sqlalchemy.orm import Session
from src.infrastructure.database.models import ReturnApplicationSnapshotORM


class ReturnsRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def save_snapshots(self, records: list[dict[str, Any]]) -> int:
        inserted = 0
        for item in records:
            waybill_no = (item.get("waybill_no") or "").strip().upper()
            source_status = self._to_int(item.get("source_status"))
            apply_time = item.get("apply_time") or ""
            if not waybill_no:
                continue

            exists = (
                self.session.query(ReturnApplicationSnapshotORM)
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
            self.session.add(row)
            inserted += 1

        if inserted > 0:
            self.session.commit()

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

        query = self.session.query(ReturnApplicationSnapshotORM)

        if status is not None:
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
