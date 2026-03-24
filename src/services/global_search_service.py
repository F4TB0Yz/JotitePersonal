import re
from typing import Optional

from src.jt_api.client import JTClient
from src.services.novedades_service import NovedadesService
from src.infrastructure.repositories.novedades_repository import NovedadesRepository
from src.infrastructure.database.connection import SessionLocal

_WAYBILL_PATTERN = re.compile(r"[A-Za-z0-9\-]{6,32}")


def _normalize_waybill_record(waybill_no: str, details: dict) -> dict:
    return {
        "waybill_no": waybill_no,
        "receiver": details.get("receiverName") or details.get("receiver") or "N/A",
        "city": details.get("receiverCity") or "N/A",
        "address": details.get("receiverDetailedAddress") or details.get("address") or "N/A",
        "sender": details.get("senderName") or details.get("sender") or "N/A",
        "order_source": details.get("orderSource") or "N/A",
    }


class GlobalSearchService:
    """
    Orchestrates a cross-domain search across waybills, messengers,
    and novedades. Receives all dependencies via constructor (DI).
    """

    def __init__(self, jt_client: JTClient, max_items: int) -> None:
        self._client = jt_client
        self._max_items = max_items

    def search(self, query: str) -> dict:
        waybill_results = self._search_waybills(query)
        messenger_results = self._search_messengers(query)
        novedades_results = self._search_novedades(query)
        return {
            "waybills": waybill_results[: self._max_items],
            "messengers": messenger_results[: self._max_items],
            "novedades": novedades_results[: self._max_items],
        }

    # ── Private domain helpers ───────────────────────────────────────────────

    def _search_waybills(self, query: str) -> list[dict]:
        if not _WAYBILL_PATTERN.fullmatch(query):
            return []
        try:
            waybill_no = query.upper()
            resp = self._client.get_order_detail(waybill_no)
            if resp.get("code") != 1:
                return []
            details = resp.get("data", {}).get("details", {})
            if not details:
                return []
            return [_normalize_waybill_record(waybill_no, details)]
        except Exception:
            return []

    def _search_messengers(self, query: str) -> list[dict]:
        try:
            resp = self._client.search_messengers(query)
            if resp.get("code") != 1 or "data" not in resp:
                return []
            data = resp["data"]
            records = data.get("records", []) if isinstance(data, dict) else (data or [])
            return records[: self._max_items]
        except Exception:
            return []

    def _search_novedades(self, query: str) -> list[dict]:
        try:
            with SessionLocal() as db:
                repo = NovedadesRepository(db)
                svc = NovedadesService(repo)
                return svc.search_novedades(query, limit=self._max_items)
        except Exception:
            return []
