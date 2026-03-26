from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class JTWaybillDetail:
    waybill_no: str
    order_source: str
    sender_name: str
    receiver_name: str
    receiver_city: str
    weight: float
    input_time: str
    dispatch_network: str

@dataclass
class TrackingEvent:
    time: str
    type_name: str
    network_name: str
    scan_network_id: str = ""
    staff_name: Optional[str] = None
    staff_contact: Optional[str] = None
    status: str = ""
    content: str = ""
    code: Optional[int] = None
    remark3: Optional[str] = None
    scan_by_code: Optional[str] = None
    next_stop_name: str = ""
    remark1: Optional[str] = None

@dataclass
class AbnormalScan:
    time: str
    type_name: str
    remark: Optional[str] = None
    operator_name: Optional[str] = None

@dataclass
class ConsolidatedReportRow:
    waybill_no: str
    status: str
    order_source: str
    sender: str
    receiver: str
    city: str
    weight: float
    last_event_time: str
    last_network: str
    last_staff: str
    staff_contact: str
    is_delivered: bool = False
    is_out_of_jurisdiction: bool = False
    arrival_punto6_time: str = "N/A"
    delivery_time: str = "N/A"
    address: str = "N/A"
    phone: str = ""
    exceptions: str = ""
    last_remark: str = ""
    signer_name: str = ""
    last_exception_reason: str = ""

def is_pending_at_network(events: List[TrackingEvent], target_network: str = "Cund-Punto6") -> bool:
    """
    Pure domain specification: A waybill is 'Pending' at a specific network ONLY if 
    it has an entry event (Arribo/Descarga) and NO exit or closure events.
    """
    # 1. Exclusion Rules (Early Returns)
    # Check if ANY event indicates the package is no longer pending at the target node.
    for e in events:
        code_str = str(e.code) if e.code is not None else ""
        type_name = e.type_name or ""
        net_name = e.network_name or ""

        # A. Cycle Closure (Delivered/Signed)
        if code_str == "100" or type_name == "Paquete firmado":
            return False
            
        # B. Network Exit / Dispatch (Carga y expedición) originating from target
        if (code_str == "1" or type_name == "Carga y expedición") and net_name == target_network:
            return False
            
        # C. Declared Return (Devolución)
        if code_str in ("170", "172") or type_name in ("Registro de devolución", "Escaneo de devolución"):
            return False

    # 2. Inclusion Rule
    # Must have at least one valid entry scan at the target network to be considered pending there.
    has_inclusion = any(
        (str(e.code) in ("2", "20") or e.type_name in ("Descarga TR1/2", "Arribo a PDV"))
        and e.network_name == target_network
        for e in events
    )

    return has_inclusion
