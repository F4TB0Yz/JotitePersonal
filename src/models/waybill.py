from dataclasses import dataclass, field
from typing import List, Optional

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
    arrival_punto6_time: str = "N/A"
    delivery_time: str = "N/A"
    address: str = "N/A"
    phone: str = ""
    exceptions: str = ""
    last_remark: str = ""
    signer_name: str = ""
    prediction_score: int = 0
    risk_level: str = "Bajo"
