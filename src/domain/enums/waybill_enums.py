from enum import Enum
from typing import Optional, Tuple
import unicodedata

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


def _normalize_network_name(name: str) -> str:
    """
    Normalizes a network name for robust comparison:
    - Decomposes Unicode (NFKD) and strips combining characters (tildes, accents).
    - Lowercases via casefold (locale-aware lowercasing).
    - Collapses all whitespace to a single space and strips edges.

    Examples:
        "Bogotá"     -> "bogota"
        "BOGOTA"     -> "bogota"
        "Cund-Punto6" -> "cund-punto6"
    """
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_only.casefold().split())


# Canonical token sets that match every observed J&T API variant.
# Add new variants here without touching business-rule code.
_BOGOTA_TOKENS: frozenset[str] = frozenset({
    "bogota",
    "bogota centro",
    "bogota-centro",
    "bogota d.c",
    "bogota dc",
})

_CENTRO_TOKENS: frozenset[str] = frozenset({
    "centro",
    "bogota centro",
    "bogota-centro",
})


def is_bogota_network(network_name: str) -> bool:
    """
    Returns True when *network_name* refers to the Bogotá metropolitan node,
    regardless of the accents, casing, or spacing used by the J&T API.

    Pure domain predicate — no infrastructure dependencies.

    Args:
        network_name: Raw scanNetworkName value from the API.
    """
    if not network_name:
        return False
    normalized = _normalize_network_name(network_name)
    return any(token in normalized for token in _BOGOTA_TOKENS)


def is_centro_network(network_name: str) -> bool:
    """
    Returns True when *network_name* refers to a Centro sub-node,
    regardless of the accents, casing, or spacing used by the J&T API.

    Pure domain predicate — no infrastructure dependencies.

    Args:
        network_name: Raw scanNetworkName value from the API.
    """
    if not network_name:
        return False
    normalized = _normalize_network_name(network_name)
    return any(token in normalized for token in _CENTRO_TOKENS)


class DateModeEnum(str, Enum):
    ASSIGNMENT = "assignment"
    ARRIVAL = "arrival"


# Ordered field-name priority lists used by WaybillNetworkService._resolve_date.
# Keeping them here prevents magic strings from leaking into the service layer.
DATE_FIELDS_BY_MODE: dict[str, Tuple[str, ...]] = {
    DateModeEnum.ASSIGNMENT: (
        "deliveryScanTimeLatest",
        "dispatchTime",
        "assignTime",
        "deliveryTime",
        "operateTime",
        "destArrivalTime",
        "dateTime",
        "deadLineTime",
        "createTime",
        "updateTime",
        "scanTime",
    ),
    DateModeEnum.ARRIVAL: (
        "destArrivalTime",
        "arrivalTime",
        "arriveTime",
        "inboundTime",
        "dispatchTime",
        "operateTime",
        "updateTime",
    ),
}
