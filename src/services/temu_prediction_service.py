import asyncio
import json
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_

from src.infrastructure.database.connection import SessionLocal, initialize_database
from src.infrastructure.database.models import TemuPredictionORM
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.jt_api.client import JTClient
from src.services.notification_service import notification_manager


class TemuPredictionService:
    def __init__(
        self,
        poll_minutes: int = 20,
        jitter_seconds: int = 120,
        cooldown_hours: int = 12,
        stale_cycles: int = 3,
    ):
        self.poll_minutes = poll_minutes
        self.jitter_seconds = jitter_seconds
        self.cooldown_hours = cooldown_hours
        self.stale_cycles = stale_cycles
        self._task = None
        self._stopping = False
        self._failure_count = 0

    @staticmethod
    def _parse_timezone(tz_string: str | None) -> timezone:
        match = re.match(r"GMT([+-])(\d{2})(\d{2})", tz_string or "")
        if not match:
            return timezone.utc
        sign = 1 if match.group(1) == "+" else -1
        hours = int(match.group(2))
        minutes = int(match.group(3))
        return timezone(sign * timedelta(hours=hours, minutes=minutes))

    @staticmethod
    def _parse_datetime(value: str | None, tzinfo: timezone) -> datetime | None:
        if not value:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(value.strip(), fmt).replace(tzinfo=tzinfo)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_over_hour(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value)
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _serialize_payload(record: dict[str, Any], hours_since: float, predicted_at: datetime) -> dict[str, Any]:
        return {
            "billcode": record.get("billcode"),
            "operateTime": record.get("operateTime"),
            "operateType": record.get("operateType"),
            "problemOperateType": record.get("problemOperateType"),
            "overTimeType": record.get("overTimeType"),
            "operateAgentName": record.get("operateAgentName"),
            "operateNetworkName": record.get("operateNetworkName"),
            "dutyName": record.get("dutyName"),
            "managerDesc": record.get("managerDesc"),
            "customerName": record.get("customerName"),
            "goodsName": record.get("goodsName"),
            "weight": record.get("weight"),
            "staff": record.get("operateUserName"),
            "hoursSinceEvent": round(hours_since, 2),
            "hoursToThreshold": round(max(96 - hours_since, 0), 2),
            "status": "breached" if hours_since >= 96 else "warning",
            "predicted96At": predicted_at.isoformat(),
        }

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stopping = True
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        await asyncio.sleep(2)
        while not self._stopping:
            try:
                await self._tick()
                self._failure_count = 0
            except Exception:
                self._failure_count += 1

            base_wait = self.poll_minutes * 60
            jitter = random.randint(-self.jitter_seconds, self.jitter_seconds)
            backoff = min((2 ** self._failure_count) * 60, 60 * 60 * 2)
            wait_seconds = max(60, base_wait + jitter + backoff)
            await asyncio.sleep(wait_seconds)

    async def _tick(self) -> None:
        with SessionLocal() as session:
            config_repo = ConfigRepository(session)
            config = config_repo.load_config()
        client = JTClient(config=config)
        tzinfo = self._parse_timezone(client.config.get("timezone"))
        now = datetime.now(tzinfo)

        detail_response = client.get_temu_monitor_detail(
            over_time_types=["72小时"],
            size=300,
        )
        records = detail_response.get("data", {}).get("records") or []
        seen_billcodes: set[str] = set()
        notifications: list[dict[str, Any]] = []

        stale_limit = now - timedelta(minutes=self.poll_minutes * self.stale_cycles)

        with SessionLocal() as session:
            for record in records:
                billcode = (record.get("billcode") or "").strip()
                if not billcode:
                    continue
                seen_billcodes.add(billcode)

                parsed_hours = self._parse_over_hour(record.get("overHour"))
                if parsed_hours is None:
                    operate_time = self._parse_datetime(record.get("operateTime"), tzinfo)
                    if not operate_time:
                        continue
                    parsed_hours = max((now - operate_time).total_seconds() / 3600, 0)

                predicted_at = now + timedelta(hours=max(96 - parsed_hours, 0))
                payload = self._serialize_payload(record, parsed_hours, predicted_at)

                row = session.query(TemuPredictionORM).filter(TemuPredictionORM.billcode == billcode).first()
                if not row:
                    row = TemuPredictionORM(
                        billcode=billcode,
                        status="active",
                        first_seen_at=now,
                        last_seen_at=now,
                        predicted_96_at=predicted_at,
                        last_hours_since=f"{parsed_hours:.2f}",
                        payload_json=json.dumps(payload, ensure_ascii=False),
                    )
                    session.add(row)
                else:
                    row.last_seen_at = now
                    row.predicted_96_at = predicted_at
                    row.last_hours_since = f"{parsed_hours:.2f}"
                    row.payload_json = json.dumps(payload, ensure_ascii=False)
                    if row.status == "resolved":
                        row.status = "active"

                if predicted_at <= now:
                    should_notify = (
                        row.notified_at is None
                        or (now - row.notified_at) >= timedelta(hours=self.cooldown_hours)
                    )
                    if should_notify:
                        row.notified_at = now
                        row.status = "notified"
                        notify_payload = dict(payload)
                        notify_payload["detectedAt"] = now.isoformat()
                        notifications.append(notify_payload)

            stale_query = (
                session.query(TemuPredictionORM)
                .filter(
                    or_(
                        TemuPredictionORM.status == "active",
                        TemuPredictionORM.status == "notified",
                    ),
                    TemuPredictionORM.last_seen_at < stale_limit,
                )
            )
            if seen_billcodes:
                stale_query = stale_query.filter(TemuPredictionORM.billcode.not_in(seen_billcodes))

            stale_rows = stale_query.all()
            for row in stale_rows:
                row.status = "resolved"

            session.commit()

        for payload in notifications:
            await notification_manager.broadcast("temu_breach_predicted", payload)

    def get_recent_predictions(self, limit: int = 50) -> list[dict[str, Any]]:
        with SessionLocal() as session:
            rows = (
                session.query(TemuPredictionORM)
                .filter(or_(TemuPredictionORM.status == "active", TemuPredictionORM.status == "notified"))
                .order_by(TemuPredictionORM.predicted_96_at.asc())
                .limit(max(1, min(limit, 200)))
                .all()
            )

            output = []
            for row in rows:
                payload = json.loads(row.payload_json) if row.payload_json else {}
                payload.update(
                    {
                        "billcode": row.billcode,
                        "status_db": row.status,
                        "predicted96At": row.predicted_96_at.isoformat() if row.predicted_96_at else None,
                        "lastSeenAt": row.last_seen_at.isoformat() if row.last_seen_at else None,
                    }
                )
                output.append(payload)
            return output


temu_prediction_service = TemuPredictionService()
