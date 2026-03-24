import time
import random
import logging
from datetime import datetime

from typing import List, Optional, Set
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from src.domain.enums.waybill_enums import (
    SignTypeEnum,
    WaybillStatusEnum,
    ScanTypeNameEnum,
    NetworkCodesEnum,
    are_networks_equivalent,
    is_bogota_network,
    is_centro_network,
    DateModeEnum,
    DATE_FIELDS_BY_MODE,
)
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.jt_api.client import JTClient
from src.models.waybill import TrackingEvent

logger = logging.getLogger(__name__)

# --- Pydantic Models ---

class WaybillFilterCriteria(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    network_code: str = Field(..., alias="networkCode")
    start_time: str = Field(..., alias="startTime")
    end_time: str = Field(..., alias="endTime")
    sign_type: int = Field(SignTypeEnum.PENDING.value, alias="signType")
    target_staff: Optional[str] = None
    target_date: Optional[str] = None
    date_mode: str = Field(default=DateModeEnum.ASSIGNMENT, alias="dateMode")

class WaybillDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    waybill_no: str  = Field(serialization_alias="waybillNo")
    status: str      = Field(serialization_alias="status")
    date: str        = Field(serialization_alias="date")
    staff: str       = Field(serialization_alias="staff")
    city: str        = Field(default="N/A", serialization_alias="city")
    receiver: str    = Field(default="N/A", serialization_alias="receiver")
    address: str     = Field(default="N/A", serialization_alias="address")
    phone: str       = Field(default="N/A", serialization_alias="phone")

class DashboardRowDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    staff: str
    total: int
    dates: dict[str, int]
    overdue_dates: List[str] = Field(default=[], serialization_alias="overdueDates")
    overdue_5_days: int = Field(default=0, serialization_alias="old")

class DashboardSummaryDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_packages: int  = Field(serialization_alias="total")
    total_staff: int     = Field(serialization_alias="totalStaff")
    dates: List[str]
    overdue_5_days: int  = Field(default=0, serialization_alias="old")
    unassigned: int      = Field(default=0, serialization_alias="unassigned")

class DashboardMatrixResponse(BaseModel):
    summary: DashboardSummaryDTO
    rows: List[DashboardRowDTO]

class NetworkWaybillRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    waybill_no: Optional[str] = Field(None, alias="waybillNo")
    bill_code: Optional[str] = Field(None, alias="billCode")
    order_id: Optional[str] = Field(None, alias="orderId")
    scan_network_id: Optional[str] = Field(None, alias="scanNetworkId")
    scan_network_name: Optional[str] = Field(None, alias="scanNetworkName")
    waybill_status: Optional[str] = Field(None, alias="waybillStatus")
    status: Optional[str] = Field(None, alias="status")
    scan_type_name: Optional[str] = Field(None, alias="scanTypeName")
    delivery_user: Optional[str] = Field(None, alias="deliveryUser")

    @property
    def canonical_waybill_no(self) -> str:
        wb = self.waybill_no or self.bill_code or self.order_id or ""
        return wb.strip().upper()

# --- Specification Pattern for Rules ---

class ExcludeRulesComposite:
    def __init__(self, network_code: str, departed_waybills: Set[str]):
        self.rules = [
            self.DepartedRule(departed_waybills),
            self.CargaExpedicionRule(network_code),
            self.DifferentNetworkRule(network_code),
            self.BogotaCentroRule(network_code),
            self.TerminalStatusRule()
        ]

    def should_exclude(self, record: NetworkWaybillRecord) -> bool:
        for rule in self.rules:
            if rule.is_satisfied_by(record):
                logger.warning(f"Guia {record.canonical_waybill_no} excluida por la regla {rule.__class__.__name__}")
                return True
        return False

    class DepartedRule:
        def __init__(self, departed: Set[str]):
            self.departed = departed
        def is_satisfied_by(self, record: NetworkWaybillRecord) -> bool:
            return record.canonical_waybill_no in self.departed

    class CargaExpedicionRule:
        def __init__(self, network_code: str):
            self.network_code = network_code
        def is_satisfied_by(self, record: NetworkWaybillRecord) -> bool:
            r_type = record.scan_type_name or ""
            r_net_id = record.scan_network_id or ""
            r_net_name = record.scan_network_name or ""
            if ScanTypeNameEnum.CARGA_EXPEDICION.value in r_type:
                if r_net_id == NetworkCodesEnum.CUND_PUNTO6.value or r_net_id == str(self.network_code) or "Cund-Punto6" in r_net_name:
                    return True
            return False

    class DifferentNetworkRule:
        def __init__(self, network_code: str):
            self.network_code = network_code
        def is_satisfied_by(self, record: NetworkWaybillRecord) -> bool:
            r_net_id = record.scan_network_id or ""
            if r_net_id and self.network_code and not are_networks_equivalent(r_net_id, self.network_code):
                return True
            return False

    class BogotaCentroRule:
        """Excludes records whose scan network is a Bogotá/Centro node
        when the current node is NOT itself in the Bogotá metropolitan area.
        Uses normalised domain predicates — immune to API casing/accent variations."""

        def __init__(self, network_code: str) -> None:
            self._current_is_bogota = is_bogota_network(str(network_code))

        def is_satisfied_by(self, record: NetworkWaybillRecord) -> bool:
            r_net_name = record.scan_network_name or ""
            scan_is_bogota_zone = is_bogota_network(r_net_name) or is_centro_network(r_net_name)
            return scan_is_bogota_zone and not self._current_is_bogota

    class TerminalStatusRule:
        def is_satisfied_by(self, record: NetworkWaybillRecord) -> bool:
            r_type = record.scan_type_name or ""
            r_status = record.waybill_status or record.status or ""
            terminals = [
                WaybillStatusEnum.ENTREGADO.value, 
                WaybillStatusEnum.DEVUELTO.value, 
                WaybillStatusEnum.FIRMADO.value, 
                WaybillStatusEnum.ANULADO.value
            ]
            return any(x in r_type or x in r_status for x in terminals)

# --- Background Worker ---

class WaybillHealerWorker:
    """
    Heals stale waybills by fetching their latest tracking events from the
    J&T API and persisting them locally.  All dependencies are injected via
    the constructor — no global look-ups, fully testable.
    """

    def __init__(self, client: JTClient, repo: TrackingEventRepository) -> None:
        self._client = client
        self._repo = repo

    def heal_stale_waybills(self, waybills: List[str]) -> None:
        for wb in waybills:
            if not wb:
                continue
            try:
                resp = self._client.get_tracking_list(wb)
                events = self._extract_events(resp)
                if events:
                    self._repo.save_events(wb, events)
            except Exception:
                pass
            finally:
                time.sleep(0.5)

    @staticmethod
    def _extract_events(resp: dict) -> List[TrackingEvent]:
        """Pure parser: API response dict → List[TrackingEvent]."""
        data_list = resp.get("data") or []
        if not (data_list and isinstance(data_list, list)):
            return []
        details = data_list[0].get("details", [])
        return [
            TrackingEvent(
                time=d.get("scanTime"),
                type_name=d.get("scanTypeName"),
                network_name=d.get("scanNetworkName"),
                scan_network_id=d.get("scanNetworkId"),
                staff_name=d.get("staffName") or d.get("scanByName"),
                staff_contact=d.get("staffContact") or "",
                status=d.get("status"),
                content=d.get("waybillTrackingContent"),
                code=d.get("code"),
            )
            for d in details
        ]

# --- Service ---

class WaybillNetworkService:
    def __init__(self, jt_client: JTClient, tracking_repo: TrackingEventRepository) -> None:
        self.jt_client = jt_client
        self.tracking_repo = tracking_repo

    def _normalize_staff(self, delivery_user: Optional[str]) -> str:
        if not delivery_user or not delivery_user.strip():
            return "Sin enrutar"
        return delivery_user.strip()

    def _resolve_date(self, record: dict, mode: str) -> str:
        fields: tuple[str, ...] = DATE_FIELDS_BY_MODE.get(mode, DATE_FIELDS_BY_MODE[DateModeEnum.ASSIGNMENT])
        for field in fields:
            val = record.get(field)
            if val and str(val) != 'N/A':
                return str(val)[:10]
        return 'Sin Fecha'

    def _map_raw_to_dto(self, r_raw: dict, mode: str) -> WaybillDTO:
        """Pure mapper: raw API dict → typed WaybillDTO. No side effects."""
        return WaybillDTO(
            waybill_no=(
                r_raw.get("waybillNo") or r_raw.get("billCode")
                or r_raw.get("orderId") or "Desconocido"
            ),
            status=(
                r_raw.get("waybillStatus") or r_raw.get("status")
                or r_raw.get("statusName") or "Pendiente"
            ),
            date=self._resolve_date(r_raw, mode),
            staff=self._normalize_staff(
                r_raw.get("deliveryUser") or r_raw.get("staffName")
            ),
            # J&T uses both receive* and receiver* variants across endpoints.
            city=(
                r_raw.get("receiveCityName") or r_raw.get("receiverCityName")
                or r_raw.get("receiverCity") or r_raw.get("city") or "N/A"
            ),
            receiver=(
                r_raw.get("receiveName") or r_raw.get("receiverName")
                or r_raw.get("customerName") or r_raw.get("receiver") or "N/A"
            ),
            address=(
                r_raw.get("receiveAddress") or r_raw.get("receiverAddress")
                or r_raw.get("receiverAddressDetail") or r_raw.get("address") or "N/A"
            ),
            phone=(
                r_raw.get("receiveMobile") or r_raw.get("receiverPhone")
                or r_raw.get("receiverMobile") or r_raw.get("phone") or "N/A"
            ),
        )

    def _apply_filters(
        self, waybills: List[WaybillDTO], criteria: WaybillFilterCriteria
    ) -> List[WaybillDTO]:
        """Applies staff and date filters independently.

        Each criterion is optional: if absent (empty / None / 'ALL'), that
        dimension is left unfiltered. The two filters are composed sequentially.
        """
        result = waybills

        if criteria.target_staff and criteria.target_staff.upper() != "ALL":
            result = [wb for wb in result if wb.staff == criteria.target_staff]

        if criteria.target_date:
            result = [wb for wb in result if wb.date == criteria.target_date]

        return result

    def _build_matrix(self, waybills: List[WaybillDTO]) -> DashboardMatrixResponse:
        """Pure aggregation: List[WaybillDTO] → staff × date matrix."""
        staff_map: dict[str, dict] = {}
        all_dates: set[str] = set()

        today = datetime.utcnow().date()
        overdue_count = 0

        for wb in waybills:
            all_dates.add(wb.date)
            entry = staff_map.setdefault(wb.staff, {"total": 0, "dates": {}, "overdue_5_days": 0, "overdue_set": set()})
            entry["total"] += 1
            entry["dates"][wb.date] = entry["dates"].get(wb.date, 0) + 1

            # Count packages older than 5 days; skip unparseable dates gracefully.
            try:
                if wb.date and wb.date != "Sin Fecha":
                    delta = (today - datetime.strptime(wb.date[:10], "%Y-%m-%d").date()).days
                    if delta > 5:
                        overdue_count += 1
                        entry["overdue_5_days"] += 1
                        entry["overdue_set"].add(wb.date)
            except (ValueError, TypeError):
                pass

        _SIN_ENRUTAR = "Sin enrutar"

        def _sort_key(r: DashboardRowDTO) -> tuple:
            # Pin 'Sin enrutar' to the bottom; rest sorted by total descending.
            return (1 if r.staff == _SIN_ENRUTAR else 0, -r.total)

        rows = sorted(
            [DashboardRowDTO(
                staff=s, 
                total=d["total"], 
                dates=d["dates"], 
                overdue_dates=sorted(list(d["overdue_set"])),
                overdue_5_days=d["overdue_5_days"]
            ) for s, d in staff_map.items()],
            key=_sort_key,
        )

        unassigned = staff_map.get(_SIN_ENRUTAR, {}).get("total", 0)

        return DashboardMatrixResponse(
            summary=DashboardSummaryDTO(
                total_packages=len(waybills),
                total_staff=len(rows),
                dates=sorted(all_dates),
                overdue_5_days=overdue_count,
                unassigned=unassigned,
            ),
            rows=rows,
        )

    def _deduplicate_waybills(self, waybills: List[WaybillDTO]) -> List[WaybillDTO]:
        """Ensures '1 waybill = 1 item' by taking the latest event mapping."""
        unique_map = {}
        for wb in waybills:
            clean_no = wb.waybill_no.strip() if wb.waybill_no else ""
            if clean_no and clean_no != "Desconocido":
                wb.waybill_no = clean_no
                unique_map[clean_no] = wb
        return list(unique_map.values())

    def _get_valid_waybills(
        self, criteria: WaybillFilterCriteria, background_tasks: Optional[BackgroundTasks] = None
    ) -> List[WaybillDTO]:
        """Single Source of Truth pipeline: fetch -> exclude -> map -> deduplicate -> filter."""
        response = self.jt_client.get_network_signing_detail(
            network_code=criteria.network_code,
            start_time=criteria.start_time,
            end_time=criteria.end_time,
            sign_type=criteria.sign_type
        )
        records_raw = response.get("data", {}).get("records", []) or []

        # If not pending, bypass strict rules
        if not records_raw or criteria.sign_type != SignTypeEnum.PENDING.value:
            raw_waybills = [self._map_raw_to_dto(r, criteria.date_mode) for r in records_raw]
            waybills = self._deduplicate_waybills(raw_waybills)
            return self._apply_filters(waybills, criteria)

        records = [NetworkWaybillRecord(**r) for r in records_raw]
        waybill_nos = [r.canonical_waybill_no for r in records if r.canonical_waybill_no]

        if not waybill_nos:
            return []

        departed = self.tracking_repo.get_departed_waybills(waybill_nos, current_network_id=criteria.network_code)

        if not departed:
            if background_tasks:
                self._enqueue_healing(mandatory=waybill_nos, periodic=[], background_tasks=background_tasks)
            raw_waybills = [self._map_raw_to_dto(r, criteria.date_mode) for r in records_raw]
            waybills = self._deduplicate_waybills(raw_waybills)
            return self._apply_filters(waybills, criteria)

        rules = ExcludeRulesComposite(criteria.network_code, departed)
        filtered_raw = []
        filtered = []

        for r_obj, r_raw in zip(records, records_raw):
            if not r_obj.canonical_waybill_no:
                continue
            if rules.should_exclude(r_obj):
                continue
            filtered_raw.append(r_raw)
            filtered.append(r_obj)

        survivors = [r.canonical_waybill_no for r in filtered]
        
        if survivors:
            staff_map = self._enrich_latest_messenger(filtered)
            for r_obj, r_raw in zip(filtered, filtered_raw):
                if r_obj.delivery_user:
                    r_raw["deliveryUser"] = r_obj.delivery_user

            if background_tasks:
                mandatory = [wb for wb in survivors if wb not in staff_map]
                periodic = [wb for wb in survivors if wb in staff_map]
                self._enqueue_healing(mandatory, periodic, background_tasks)

        raw_waybills = [self._map_raw_to_dto(r, criteria.date_mode) for r in filtered_raw]
        waybills = self._deduplicate_waybills(raw_waybills)
        return self._apply_filters(waybills, criteria)

    def get_network_waybills(
        self, criteria: WaybillFilterCriteria, background_tasks: BackgroundTasks
    ) -> DashboardMatrixResponse:
        waybills = self._get_valid_waybills(criteria, background_tasks)
        return self._build_matrix(waybills)

    def get_cell_details(
        self, criteria: WaybillFilterCriteria, background_tasks: BackgroundTasks
    ) -> List[WaybillDTO]:
        return self._get_valid_waybills(criteria, background_tasks)

    def _enrich_latest_messenger(self, records: List[NetworkWaybillRecord]) -> dict:
        if not records:
            return {}
        waybill_nos = [r.canonical_waybill_no for r in records if r.canonical_waybill_no]
        staff_map = self.tracking_repo.get_latest_delivery_events(waybill_nos)
        for r in records:
            wb = r.canonical_waybill_no
            if wb in staff_map:
                r.delivery_user = staff_map[wb]
        return staff_map

    def _enqueue_healing(
        self, mandatory: List[str], periodic: List[str], background_tasks: BackgroundTasks
    ) -> None:
        to_process = list(mandatory)
        if periodic:
            to_process += random.sample(periodic, min(10, len(periodic)))
        if not to_process:
            return

        def _run_healing(waybills: List[str]) -> None:
            config = ConfigRepository.get_cached()
            client = JTClient(config=config)
            with SessionLocal() as db:
                repo = TrackingEventRepository(db)
                WaybillHealerWorker(client, repo).heal_stale_waybills(waybills)

        background_tasks.add_task(_run_healing, to_process)
