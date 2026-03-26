import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from src.jt_api.client import JTClient


class TemuAlertService:
    """Genera reportes de alertas para guías TEMU cercanas a 96 horas sin actualización."""

    DEFAULT_PROBLEM_TYPES = [
        "快件揽收",
        "入仓扫描",
        "发件扫描",
        "到件扫描",
        "中心到件",
        "集货到件",
        "出仓扫描",
        "代理点收入扫描",
        "问题件扫描",
        "建包扫描",
        "转第三方"
    ]

    DEFAULT_OVER_TIME_TYPES = ["72小时", "96小时"]

    def __init__(self, client: JTClient):
        self.client = client
        self.tzinfo = self._resolve_timezone(client.config.get("timezone"))

    @staticmethod
    def _resolve_timezone(tz_string: Optional[str]) -> timezone:
        tz_string = tz_string or ""
        # Manejo explícito de Colombia para evitar fallbacks erróneos a UTC en servidores
        if "Bogota" in tz_string or "Bogotá" in tz_string or tz_string == "America/Bogota":
            return timezone(timedelta(hours=-5))

        match = re.match(r"GMT([+-])(\d{2})(\d{2})", tz_string)
        if match:
            sign = 1 if match.group(1) == "+" else -1
            hours = int(match.group(2))
            minutes = int(match.group(3))
            delta = timedelta(hours=hours, minutes=minutes) * sign
            return timezone(delta)
        # fallback al timezone local si está disponible
        try:
            return datetime.now().astimezone().tzinfo or timezone.utc
        except Exception:
            return timezone.utc

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value or not value.strip():
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                dt = datetime.strptime(value.strip(), fmt)
                return dt.replace(tzinfo=self.tzinfo)
            except ValueError:
                continue
        return None

    def _categorize_records(
        self,
        records: List[Dict[str, Any]],
        threshold_hours: float,
        window_hours: float,
        include_overdue: bool
    ) -> Dict[str, Any]:
        now = datetime.now(self.tzinfo)
        
        # 1. Deduplicación por billcode (tomar el evento más reciente si hay duplicados)
        # Y filtrado opcional de guías que ya tienen un escaneo de problema ("handled")
        unique_latest: Dict[str, Dict[str, Any]] = {}
        for r in records:
            bc = (r.get("billcode") or "").strip()
            if not bc:
                continue
            
            # Omitir guías cuyo último evento reportado sea un problema (novedad)
            # J&T suele mover estas fuera del monitor de "pendiente" de 96h
            if r.get("problemOperateType") == "问题件扫描":
                continue

            if bc in unique_latest:
                current_time = self._parse_datetime(r.get("operateTime"))
                existing_time = self._parse_datetime(unique_latest[bc].get("operateTime"))
                if current_time and existing_time and current_time > existing_time:
                    unique_latest[bc] = r
            else:
                unique_latest[bc] = r

        warnings: List[Dict[str, Any]] = []
        breached: List[Dict[str, Any]] = []

        for record in unique_latest.values():
            operate_time = self._parse_datetime(record.get("operateTime"))
            if not operate_time:
                continue

            hours_since = (now - operate_time).total_seconds() / 3600
            if hours_since < 0:
                continue

            hours_since = round(hours_since, 2)
            hours_to_threshold = round(max(threshold_hours - hours_since, 0), 2)
            base_payload = {
                "billcode": record.get("billcode"),
                "operateTime": record.get("operateTime"),
                "operateType": record.get("operateType"),
                "problemOperateType": record.get("problemOperateType"),
                "overTimeType": record.get("overTimeType"),
                "overHour": record.get("overHour"),
                "operateAgentName": record.get("operateAgentName"),
                "operateNetworkName": record.get("operateNetworkName"),
                "dutyName": record.get("dutyName"),
                "managerDesc": record.get("managerDesc"),
                "customerName": record.get("customerName"),
                "goodsName": record.get("goodsName"),
                "weight": record.get("weight"),
                "staff": record.get("operateUserName"),
                "hoursSinceEvent": hours_since,
                "hoursToThreshold": hours_to_threshold,
            }

            if hours_since >= threshold_hours:
                if include_overdue:
                    breached.append({**base_payload, "status": "breached"})
                continue
            elif threshold_hours - hours_since <= window_hours:
                warnings.append({**base_payload, "status": "warning"})

        warnings.sort(key=lambda item: (item["hoursToThreshold"], -item["hoursSinceEvent"]))
        breached.sort(key=lambda item: (-item["hoursSinceEvent"], item["billcode"] or ""))

        return {
            "warnings": warnings,
            "breached": breached,
            "warningCount": len(warnings),
            "breachedCount": len(breached)
        }

    def build_alert_report(
        self,
        threshold_hours: float = 96,
        window_hours: float = 12,
        include_overdue: bool = True,
        over_time_types: Optional[List[str]] = None,
        duty_agent_code: str = "R00001",
        duty_code: str = "1025006",
        manager_code: str = "108108",
        responsible_org_code: str = "1025006",
        dimension_type: int = 2,
        detail_page_size: int = 200
    ) -> Dict[str, Any]:
        summary_response = self.client.get_temu_monitor_summary(
            dimension_type=dimension_type,
            responsible_org_code=responsible_org_code
        )
        summary_records = summary_response.get("data", {}).get("records") or []
        summary_record = summary_records[0] if summary_records else {}

        detail_response = self.client.get_temu_monitor_detail(
            over_time_types=over_time_types or self.DEFAULT_OVER_TIME_TYPES,
            duty_agent_code=duty_agent_code,
            duty_code=duty_code,
            manager_code=manager_code,
            problem_operate_types=self.DEFAULT_PROBLEM_TYPES,
            size=detail_page_size
        )
        detail_records = detail_response.get("data", {}).get("records") or []

        categorized = self._categorize_records(
            detail_records,
            threshold_hours=threshold_hours,
            window_hours=window_hours,
            include_overdue=include_overdue
        )

        return {
            "generatedAt": datetime.now(self.tzinfo).isoformat(),
            "thresholdHours": threshold_hours,
            "windowHours": window_hours,
            "totalCandidates": len(detail_records),
            "warningCount": categorized["warningCount"],
            "breachedCount": categorized["breachedCount"],
            "alerts": categorized["breached"] + categorized["warnings"],
            "summary": summary_record,
            "metadata": {
                "dutyAgentCode": duty_agent_code,
                "dutyCode": duty_code,
                "managerCode": manager_code,
                "responsibleOrgCode": responsible_org_code,
                "dimensionType": dimension_type,
                "includeOverdue": include_overdue,
                "overTimeTypes": over_time_types or self.DEFAULT_OVER_TIME_TYPES,
            }
        }