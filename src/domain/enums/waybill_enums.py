from enum import Enum
from typing import Optional

class SignTypeEnum(int, Enum):
    PENDING = 0
    SIGNED = 1

class WaybillStatusEnum(str, Enum):
    ENTREGADO = "Entregado"
    DEVUELTO = "Devuelto"
    FIRMADO = "Firmado"
    ANULADO = "Anulado"

class ScanTypeNameEnum(str, Enum):
    CARGA_EXPEDICION = "Carga y expedición"

class NetworkCodesEnum(str, Enum):
    CUND_PUNTO6 = "1009"
    BOGOTA = "Bogota"
    CENTRO = "Centro"

NETWORK_EQUIVALENCES = {
    "1009": {"1009", "1025006"},
    "1025006": {"1009", "1025006"},
}

def are_networks_equivalent(net_a: Optional[str], net_b: Optional[str]) -> bool:
    if not net_a or not net_b:
        return False
    # Comparación estricta
    a_str = str(net_a).strip()
    b_str = str(net_b).strip()
    if a_str == b_str:
        return True
    # Comparación por equivalencias
    eq_a = NETWORK_EQUIVALENCES.get(a_str, {a_str})
    return b_str in eq_a
