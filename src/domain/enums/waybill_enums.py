from enum import Enum

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
