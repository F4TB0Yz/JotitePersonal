from pydantic import BaseModel, Field
from typing import Optional

class MessengerProfile(BaseModel):
    accountCode: Optional[str] = None
    accountName: Optional[str] = None
    customerNetworkCode: Optional[str] = None
    customerNetworkName: Optional[str] = None
    accountPhone: Optional[str] = None
    accountTel: Optional[str] = None
    accountMobile: Optional[str] = None
    contactPhone: Optional[str] = None
    contactTel: Optional[str] = None
    contactMobile: Optional[str] = None
    phone: Optional[str] = None
    mobilePhone: Optional[str] = None
    telPhone: Optional[str] = None

    def get_phone(self) -> Optional[str]:
        fields = [
            self.accountPhone, self.accountTel, self.accountMobile,
            self.contactPhone, self.contactTel, self.contactMobile,
            self.phone, self.mobilePhone, self.telPhone
        ]
        for candidate in fields:
            if candidate:
                return candidate.strip() if hasattr(candidate, 'strip') else str(candidate)
        return None

class MessengerContact(BaseModel):
    name: str = Field(..., description="Messenger name")
    accountCode: Optional[str] = Field(None, description="Account code")
    networkName: Optional[str] = Field(None, description="Network name")
    phone: Optional[str] = Field(None, description="Phone number")

class MessengerNotFoundException(Exception):
    """Excepción lanzada cuando no se encuentra el mensajero."""
    pass

class JTClientIntegrationException(Exception):
    """Excepción lanzada para errores de integración con el cliente externo."""
    pass
