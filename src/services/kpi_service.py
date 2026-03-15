import json
from collections import defaultdict
from datetime import datetime, date
from typing import Any

from src.infrastructure.repositories.kpi_repository import KPIRepository
from src.infrastructure.database.models import NovedadORM, SettlementORM


class KPIService:
    def __init__(self, repository: KPIRepository):
        self.repository = repository

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        text = str(value).strip()
        if not text:
            return None

        normalized = text.replace("T", " ").replace("Z", "")
        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        )
        for fmt in formats:
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_range(start_date: str | None, end_date: str | None) -> tuple[datetime | None, datetime | None]:
        start = KPIService._parse_datetime(start_date)
        end = KPIService._parse_datetime(end_date)
        if end:
            end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end

    def _load_settlements(self, start: datetime | None, end: datetime | None) -> list[SettlementORM]:
        return self.repository.get_settlements(start, end)

    def _load_novedades(self, start: datetime | None, end: datetime | None) -> list[NovedadORM]:
        return self.repository.get_novedades(start, end)

    def _calculate_average_delivery_hours(self, settlements: list[SettlementORM]) -> float:
        total_hours = 0.0
        count = 0
        for row in settlements:
            if not row.detail_json:
                continue
            try:
                detail = json.loads(row.detail_json)
            except Exception:
                continue
            delivered = detail.get("delivered_waybills") or []
            for item in delivered:
                dispatch_dt = self._parse_datetime(item.get("dispatchTime"))
                sign_dt = self._parse_datetime(item.get("signTime"))
                if not dispatch_dt or not sign_dt:
                    continue
                delta = sign_dt - dispatch_dt
                hours = delta.total_seconds() / 3600
                if hours < 0:
                    continue
                total_hours += hours
                count += 1
        if count == 0:
            return 0.0
        return round(total_hours / count, 2)

    def _build_ranking(self, settlements: list[SettlementORM], limit: int) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in settlements:
            key = (row.account_code or "").strip() or "SIN_CODIGO"
            if key not in grouped:
                grouped[key] = {
                    "account_code": row.account_code,
                    "account_name": row.account_name,
                    "total_waybills": 0,
                    "total_delivered": 0,
                    "total_pending": 0,
                    "total_amount": 0.0,
                    "settlements": 0,
                }
            current = grouped[key]
            current["total_waybills"] += int(row.total_waybills or 0)
            current["total_delivered"] += int(row.total_delivered or 0)
            current["total_pending"] += int(row.total_pending or 0)
            current["total_amount"] += float(row.total_amount or 0)
            current["settlements"] += 1

        ranking = []
        for item in grouped.values():
            total_waybills = item["total_waybills"]
            effectiveness = (item["total_delivered"] / total_waybills * 100) if total_waybills else 0
            ranking.append({
                **item,
                "effectiveness_rate": round(effectiveness, 2),
                "total_amount": round(item["total_amount"], 2),
            })

        ranking.sort(
            key=lambda item: (
                item["effectiveness_rate"],
                item["total_delivered"],
                item["total_waybills"],
            ),
            reverse=True,
        )
        return ranking[:max(1, min(limit, 50))]

    def _build_novedad_breakdown(self, novedades: list[NovedadORM]) -> dict[str, Any]:
        by_type: dict[str, int] = defaultdict(int)
        by_status: dict[str, int] = defaultdict(int)
        for row in novedades:
            nov_type = (row.type or "Sin tipo").strip() or "Sin tipo"
            nov_status = (row.status or "Sin estado").strip() or "Sin estado"
            by_type[nov_type] += 1
            by_status[nov_status] += 1

        top_types = [
            {"type": key, "count": value}
            for key, value in sorted(by_type.items(), key=lambda item: item[1], reverse=True)
        ]
        status_items = [
            {"status": key, "count": value}
            for key, value in sorted(by_status.items(), key=lambda item: item[1], reverse=True)
        ]
        return {
            "by_type": top_types,
            "by_status": status_items,
        }

    def _build_daily_trend(self, settlements: list[SettlementORM], novedades: list[NovedadORM]) -> list[dict[str, Any]]:
        trend_map: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "date": "",
                "settlements": 0,
                "waybills": 0,
                "delivered": 0,
                "novedades": 0,
            }
        )

        for row in settlements:
            if not row.generated_at:
                continue
            key = row.generated_at.date().isoformat()
            bucket = trend_map[key]
            bucket["date"] = key
            bucket["settlements"] += 1
            bucket["waybills"] += int(row.total_waybills or 0)
            bucket["delivered"] += int(row.total_delivered or 0)

        for row in novedades:
            if not row.created_at:
                continue
            key = row.created_at.date().isoformat()
            bucket = trend_map[key]
            bucket["date"] = key
            bucket["novedades"] += 1

        items = list(trend_map.values())
        items.sort(key=lambda item: item["date"])
        return items

    def get_overview(self, start_date: str | None = None, end_date: str | None = None, ranking_limit: int = 10) -> dict[str, Any]:
        start, end = self._normalize_range(start_date, end_date)
        settlements = self._load_settlements(start, end)
        novedades = self._load_novedades(start, end)

        total_waybills = sum(int(row.total_waybills or 0) for row in settlements)
        total_delivered = sum(int(row.total_delivered or 0) for row in settlements)
        total_pending = sum(int(row.total_pending or 0) for row in settlements)
        total_amount = sum(float(row.total_amount or 0) for row in settlements)
        effectiveness_rate = (total_delivered / total_waybills * 100) if total_waybills else 0
        avg_delivery_hours = self._calculate_average_delivery_hours(settlements)

        return {
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
            },
            "summary": {
                "settlements": len(settlements),
                "total_waybills": total_waybills,
                "total_delivered": total_delivered,
                "total_pending": total_pending,
                "effectiveness_rate": round(effectiveness_rate, 2),
                "avg_delivery_hours": avg_delivery_hours,
                "total_amount": round(total_amount, 2),
                "novedades": len(novedades),
            },
            "ranking": self._build_ranking(settlements, ranking_limit),
            "novedades": self._build_novedad_breakdown(novedades),
            "trend": self._build_daily_trend(settlements, novedades),
            "generated_at": datetime.utcnow().isoformat(),
        }