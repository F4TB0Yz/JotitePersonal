import json
from datetime import datetime
from typing import Any

from src.jt_api.client import JTClient
from src.infrastructure.repositories.returns_repository import ReturnsRepository
from src.domain.exceptions import APIError, InvalidStatusError, ValidationError


class ReturnsService:
    VALID_STATUSES = (1, 2, 3)

    def __init__(self, repository: ReturnsRepository, client: JTClient, apply_network_id: int = 1009):
        self.repository = repository
        self.client = client
        self.apply_network_id = int(apply_network_id)

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
        if source_status not in self.VALID_STATUSES:
            raise InvalidStatusError("status debe ser 1 (En revisión), 2 (Aprobada) o 3 (Rechazada)")

        response = self.client.get_return_applications_page(
            apply_network_id=self.apply_network_id,
            apply_time_from=apply_time_from,
            apply_time_to=apply_time_to,
            status=source_status,
            current=max(1, self._to_int(current, 1)),
            size=min(max(1, self._to_int(size, 20)), 100),
        )

        if response.get("code") != 1:
            raise APIError(response.get("msg") or "Error consultando devoluciones", status_code=response.get("code"))

        data = response.get("data") or {}
        records = data.get("records") or []
        synced_at = datetime.now().isoformat()

        normalized = [self._normalize_record(item, source_status, synced_at) for item in records]

        inserted_count = 0
        if save_snapshot and normalized:
            inserted_count = self.repository.save_snapshots(normalized)

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

    def fetch_printable_list(
        self,
        apply_time_from: str,
        apply_time_to: str,
        current: int = 1,
        size: int = 20,
        pring_flag: int = 0,
        printer: int = 0,
        template_size: int = 1,
        pring_type: int = 1,
    ) -> dict[str, Any]:
        response = self.client.get_return_print_list_page(
            apply_network_id=self.apply_network_id,
            apply_time_from=apply_time_from,
            apply_time_to=apply_time_to,
            current=max(1, self._to_int(current, 1)),
            size=min(max(1, self._to_int(size, 20)), 100),
            pring_flag=self._to_int(pring_flag, 0),
            printer=self._to_int(printer, 0),
            template_size=self._to_int(template_size, 1),
            pring_type=self._to_int(pring_type, 1),
        )

        if response.get("code") != 1:
            raise APIError(response.get("msg") or "Error consultando devoluciones para imprimir", status_code=response.get("code"))

        data = response.get("data") or {}
        records = data.get("records") or []
        normalized = [
            {
                "waybill_no": item.get("waybillNo") or "",
                "source_status": self._to_int(item.get("status"), 2),
                "status_name": item.get("statusName") or "",
                "apply_time": item.get("applyTime") or "",
                "examine_time": item.get("examineTime") or "",
                "apply_network_id": item.get("applyNetworkId"),
                "apply_network_name": item.get("applyNetworkName") or "",
                "apply_staff_code": item.get("applyStaffCode") or "",
                "apply_staff_name": item.get("applyStaffName") or "",
                "examine_staff_name": item.get("examineStaffName") or "",
                "reback_transfer_reason": item.get("rebackTransferReason") or "",
                "print_flag": item.get("printFlag"),
                "print_count": item.get("printCount"),
                "raw": item,
            }
            for item in records
        ]

        return {
            "records": normalized,
            "total": self._to_int(data.get("total"), len(normalized)),
            "size": self._to_int(data.get("size"), size),
            "current": self._to_int(data.get("current"), current),
            "pages": self._to_int(data.get("pages"), 0),
            "mode": "printable",
        }

    def get_print_waybill_url(
        self,
        waybill_no: str,
    ) -> dict[str, Any]:
        """
        Obtiene la URL de impresión de guías de devolución.
        Refactorizado para manejar directamente el link si 'data' es un string.
        """
        target = (waybill_no or "").strip().upper()
        if not target:
            raise ValidationError("waybill_no requerido")

        # Se eliminan parámetros obsoletos para cumplir el contrato del cliente J&T
        response = self.client.get_return_print_waybill_url_new([target])

        if response.get("code") != 1:
            raise APIError(response.get("msg") or "No se pudo obtener el link de impresión", status_code=response.get("code"))

        data = response.get("data")
        resolved_url = None

        # Validación explícita según el contrato real y retrocompatibilidad
        if isinstance(data, str) and data.startswith("http"):
            resolved_url = data
        elif isinstance(data, dict):
            resolved_url = (
                data.get("centrePrintUrl")
                or data.get("centerPrintUrl")
                or data.get("printUrl")
                or data.get("url")
            )
        elif isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                resolved_url = (
                    first.get("centrePrintUrl")
                    or first.get("centerPrintUrl")
                    or first.get("printUrl")
                    or first.get("url")
                )
            elif isinstance(first, str) and first.startswith("http"):
                resolved_url = first

        return {
            "waybill_no": target,
            "print_url": resolved_url,
            "raw": data,
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
        """List snapshots delegating to the repository."""
        valid_status = status if status in self.VALID_STATUSES else None
        return self.repository.list_snapshots(
            status=valid_status,
            waybill_no=waybill_no,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    def sync_statuses(
        self,
        apply_time_from: str,
        apply_time_to: str,
        statuses: list[int] | tuple[int, ...] = (1, 2, 3),
        size: int = 50,
        max_pages: int = 20,
    ) -> dict[str, Any]:
        statuses_to_sync = [s for s in statuses if s in self.VALID_STATUSES] or list(self.VALID_STATUSES)
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
