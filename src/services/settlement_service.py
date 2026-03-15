import json
from decimal import Decimal
from typing import Any

from src.infrastructure.database.connection import SessionLocal, initialize_database
from src.infrastructure.database.models import MessengerRateORM, SettlementORM
from src.jt_api.client import JTClient
from src.services.novedades_service import NovedadesService


class SettlementService:
    def __init__(self, client: JTClient, novedades_svc: NovedadesService):
        self.client = client
        self.novedades_svc = novedades_svc

    @staticmethod
    def _to_decimal(value: Any, default: str = "0") -> Decimal:
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal(default)

    @staticmethod
    def _is_delivered(row: dict[str, Any]) -> bool:
        value = row.get("isSign")
        if value in (1, True):
            return True
        if isinstance(value, str):
            return value.strip() in {"1", "true", "True", "SIGNED", "signed"}
        return False

    def set_rate(self, account_code: str, account_name: str, rate_per_delivery: float) -> dict[str, Any]:
        code = (account_code or "").strip()
        name = (account_name or "").strip() or code
        rate = self._to_decimal(rate_per_delivery)
        if not code:
            raise ValueError("account_code requerido")
        if rate < 0:
            raise ValueError("rate_per_delivery no puede ser negativo")

        with SessionLocal() as session:
            row = session.query(MessengerRateORM).filter(MessengerRateORM.account_code == code).first()
            if not row:
                row = MessengerRateORM(
                    account_code=code,
                    account_name=name,
                    rate_per_delivery=str(rate),
                )
                session.add(row)
            else:
                row.account_name = name
                row.rate_per_delivery = str(rate)
            session.commit()
            session.refresh(row)
            return {
                "account_code": row.account_code,
                "account_name": row.account_name,
                "rate_per_delivery": float(self._to_decimal(row.rate_per_delivery)),
            }

    def get_rate(self, account_code: str) -> dict[str, Any] | None:
        code = (account_code or "").strip()
        if not code:
            return None
        with SessionLocal() as session:
            row = session.query(MessengerRateORM).filter(MessengerRateORM.account_code == code).first()
            if not row:
                return None
            return {
                "account_code": row.account_code,
                "account_name": row.account_name,
                "rate_per_delivery": float(self._to_decimal(row.rate_per_delivery)),
            }

    def generate_settlement(
        self,
        account_code: str,
        account_name: str,
        network_code: str,
        start_time: str,
        end_time: str,
        deduction_per_issue: float = 0,
        rate_per_delivery_override: float | None = None,
    ) -> dict[str, Any]:
        code = (account_code or "").strip()
        name = (account_name or "").strip() or code
        net = (network_code or "").strip()
        if not all([code, start_time, end_time]):
            raise ValueError("Parámetros incompletos")

        override_rate = None
        if rate_per_delivery_override is not None:
            override_rate = self._to_decimal(rate_per_delivery_override)

        if override_rate is not None and override_rate >= 0:
            rate = override_rate
        else:
            rate_data = self.get_rate(code)
            rate = self._to_decimal(rate_data["rate_per_delivery"] if rate_data else 0)

        deduction_value = self._to_decimal(deduction_per_issue)

        records = self.client.get_all_messenger_waybills_detail(code, net, start_time, end_time)

        delivered_rows = [row for row in records if self._is_delivered(row)]
        pending_rows = [row for row in records if not self._is_delivered(row)]

        novedades = self.novedades_svc.get_all_novedades()
        unresolved_waybills = {
            item.get("waybill")
            for item in novedades
            if item.get("waybill") and (item.get("status") or "").lower() != "resuelto"
        }

        deduction_count = sum(1 for row in delivered_rows if row.get("waybillNo") in unresolved_waybills)
        deduction_total = deduction_value * deduction_count

        gross_total = rate * len(delivered_rows)
        total_amount = gross_total - deduction_total
        if total_amount < 0:
            total_amount = Decimal("0")

        detail = {
            "delivered_waybills": [
                {
                    "waybillNo": row.get("waybillNo"),
                    "dispatchTime": row.get("dispatchTime"),
                    "signTime": row.get("signTime"),
                    "status": row.get("status"),
                    "deduction": float(deduction_value) if row.get("waybillNo") in unresolved_waybills else 0,
                }
                for row in delivered_rows
            ],
            "pending_waybills": [
                {
                    "waybillNo": row.get("waybillNo"),
                    "dispatchTime": row.get("dispatchTime"),
                    "status": row.get("status"),
                }
                for row in pending_rows
            ],
        }

        with SessionLocal() as session:
            row = SettlementORM(
                account_code=code,
                account_name=name,
                network_code=net,
                start_time=start_time,
                end_time=end_time,
                total_waybills=len(records),
                total_delivered=len(delivered_rows),
                total_pending=len(pending_rows),
                deduction_count=deduction_count,
                deduction_total=str(deduction_total),
                rate_per_delivery=str(rate),
                total_amount=str(total_amount),
                status="borrador",
                detail_json=json.dumps(detail, ensure_ascii=False),
            )
            session.add(row)
            session.commit()
            session.refresh(row)

            return self._serialize_settlement(row)

    def list_settlements(self, account_code: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        with SessionLocal() as session:
            query = session.query(SettlementORM)
            if account_code:
                query = query.filter(SettlementORM.account_code == account_code.strip())
            rows = query.order_by(SettlementORM.generated_at.desc()).limit(max(1, min(limit, 100))).all()
            return [self._serialize_settlement(row, include_detail=False) for row in rows]

    def get_settlement(self, settlement_id: int) -> dict[str, Any] | None:
        with SessionLocal() as session:
            row = session.query(SettlementORM).filter(SettlementORM.id == settlement_id).first()
            if not row:
                return None
            return self._serialize_settlement(row)

    def update_status(self, settlement_id: int, status: str) -> bool:
        allowed = {"borrador", "aprobado", "pagado"}
        next_status = (status or "").strip().lower()
        if next_status not in allowed:
            raise ValueError("Estado inválido")

        with SessionLocal() as session:
            row = session.query(SettlementORM).filter(SettlementORM.id == settlement_id).first()
            if not row:
                return False
            row.status = next_status
            session.commit()
            return True

    def delete_settlement(self, settlement_id: int) -> bool:
        with SessionLocal() as session:
            row = session.query(SettlementORM).filter(SettlementORM.id == settlement_id).first()
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def _serialize_settlement(self, row: SettlementORM, include_detail: bool = True) -> dict[str, Any]:
        payload = {
            "id": row.id,
            "account_code": row.account_code,
            "account_name": row.account_name,
            "network_code": row.network_code,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "total_waybills": row.total_waybills,
            "total_delivered": row.total_delivered,
            "total_pending": row.total_pending,
            "deduction_count": row.deduction_count,
            "deduction_total": float(self._to_decimal(row.deduction_total)),
            "rate_per_delivery": float(self._to_decimal(row.rate_per_delivery)),
            "total_amount": float(self._to_decimal(row.total_amount)),
            "status": row.status,
            "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        }
        if include_detail:
            payload["detail"] = json.loads(row.detail_json) if row.detail_json else {"delivered_waybills": [], "pending_waybills": []}
        return payload
