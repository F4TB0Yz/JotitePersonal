import time
import random
from typing import List, Optional, Set
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from src.domain.enums.waybill_enums import SignTypeEnum, WaybillStatusEnum, ScanTypeNameEnum, NetworkCodesEnum, are_networks_equivalent
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.jt_api.client import JTClient
from src.models.waybill import TrackingEvent

# --- Pydantic Models ---

class WaybillFilterCriteria(BaseModel):
    network_code: str = Field(..., alias="networkCode")
    start_time: str = Field(..., alias="startTime")
    end_time: str = Field(..., alias="endTime")
    sign_type: int = Field(SignTypeEnum.PENDING.value, alias="signType")

    class Config:
        populate_by_name = True

class NetworkWaybillRecord(BaseModel):
    waybill_no: Optional[str] = Field(None, alias="waybillNo")
    bill_code: Optional[str] = Field(None, alias="billCode")
    order_id: Optional[str] = Field(None, alias="orderId")
    scan_network_id: Optional[str] = Field(None, alias="scanNetworkId")
    scan_network_name: Optional[str] = Field(None, alias="scanNetworkName")
    waybill_status: Optional[str] = Field(None, alias="waybillStatus")
    status: Optional[str] = Field(None, alias="status")
    scan_type_name: Optional[str] = Field(None, alias="scanTypeName")

    class Config:
        populate_by_name = True
        extra = "allow"

    @property
    def canonical_waybill_no(self) -> str:
        wb = self.waybill_no or self.bill_code or self.order_id or ""
        return wb.strip().upper()

class NetworkWaybillResponse(BaseModel):
    records: List[dict]
    _filtered_count: Optional[int] = None

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
        return any(rule.is_satisfied_by(record) for rule in self.rules)

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
        def __init__(self, network_code: str):
            self.network_code = network_code
        def is_satisfied_by(self, record: NetworkWaybillRecord) -> bool:
            r_net_name = record.scan_network_name or ""
            if (NetworkCodesEnum.BOGOTA.value in r_net_name or NetworkCodesEnum.CENTRO.value in r_net_name) and NetworkCodesEnum.BOGOTA.value not in str(self.network_code):
                return True
            return False

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
    @staticmethod
    def heal_stale_waybills(waybills: List[str]):
        if not waybills:
            return
            
        config = ConfigRepository.get_cached()
        client = JTClient(config=config)
        
        with SessionLocal() as db:
            repo = TrackingEventRepository(db)
            
            for wb in waybills:
                if not wb: continue
                try:
                    resp = client.get_tracking_list(wb)
                    data_list = resp.get("data") or []
                    details = []
                    if data_list and isinstance(data_list, list):
                        details = data_list[0].get("details", [])
                        
                    if details:
                        events = [
                            TrackingEvent(
                                time=d.get("scanTime"),
                                type_name=d.get("scanTypeName"),
                                network_name=d.get("scanNetworkName"),
                                scan_network_id=d.get("scanNetworkId"),
                                staff_name=d.get("staffName") or d.get("scanByName"),
                                staff_contact=d.get("staffContact") or "",
                                status=d.get("status"),
                                content=d.get("waybillTrackingContent"),
                                code=d.get("code")
                            ) for d in details
                        ]
                        repo.save_events(wb, events)
                    time.sleep(0.5) 
                except Exception:
                    time.sleep(0.5)
                    continue

# --- Service ---

class WaybillNetworkService:
    def __init__(self, jt_client: JTClient, tracking_repo: TrackingEventRepository, db: Session):
        self.jt_client = jt_client
        self.tracking_repo = tracking_repo
        self.db = db

    def get_network_waybills(self, criteria: WaybillFilterCriteria, background_tasks: BackgroundTasks) -> NetworkWaybillResponse:
        response = self.jt_client.get_network_signing_detail(
            network_code=criteria.network_code,
            start_time=criteria.start_time,
            end_time=criteria.end_time,
            sign_type=criteria.sign_type
        )
        records_raw = response.get("data", {}).get("records", []) or []

        if not records_raw or criteria.sign_type != SignTypeEnum.PENDING.value:
            return NetworkWaybillResponse(records=records_raw)

        records = [NetworkWaybillRecord(**r) for r in records_raw]
        waybill_nos = [r.canonical_waybill_no for r in records if r.canonical_waybill_no]

        if not waybill_nos:
            return NetworkWaybillResponse(records=records_raw)

        departed = self.tracking_repo.get_departed_waybills(
            self.db, waybill_nos, current_network_id=criteria.network_code
        )

        if not departed:
            self._enqueue_healing(waybill_nos, background_tasks)
            return NetworkWaybillResponse(records=records_raw)

        rules = ExcludeRulesComposite(criteria.network_code, departed)
        filtered = []
        filtered_raw = []

        for r_obj, r_raw in zip(records, records_raw):
            if not r_obj.canonical_waybill_no:
                continue
            if rules.should_exclude(r_obj):
                continue
            filtered_raw.append(r_raw)
            filtered.append(r_obj)

        survivors = [r.canonical_waybill_no for r in filtered]
        
        # Sobreescribir deliveryUser con el historial local detallado (Healing)
        if survivors:
            staff_map = self.tracking_repo.get_assigned_staff_map(self.db, survivors)
            for r_raw in filtered_raw:
                wb = (r_raw.get("waybillNo") or r_raw.get("billCode") or r_raw.get("orderId") or "").strip().upper()
                if wb in staff_map:
                    r_raw["deliveryUser"] = staff_map[wb]

            # Saneamiento Inteligente en segundo plano
            mandatory = [wb for wb in survivors if wb not in staff_map]
            periodic = [wb for wb in survivors if wb in staff_map]
            self._enqueue_healing(mandatory, periodic, background_tasks)

        return NetworkWaybillResponse(
            records=filtered_raw, 
            _filtered_count=len(records_raw) - len(filtered_raw)
        )

    def _enqueue_healing(self, mandatory: List[str], periodic: List[str], background_tasks: BackgroundTasks):
        to_process = list(mandatory)
        if periodic:
            to_process += random.sample(periodic, min(10, len(periodic)))
            
        if to_process:
            background_tasks.add_task(WaybillHealerWorker.heal_stale_waybills, to_process)
