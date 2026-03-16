import os
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.repositories.config_repository import ConfigRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["Config"])

class TokenPayload(BaseModel):
    authToken: str

@router.post("/token")
async def sync_token(payload: TokenPayload, x_sync_key: str = Header(None, alias="X-Sync-Key")):
    correct_key = os.getenv("SYNC_API_KEY")
    if not correct_key:
        raise HTTPException(status_code=500, detail="SYNC_API_KEY no configurado en servidor")
        
    if x_sync_key != correct_key:
        raise HTTPException(status_code=403, detail="Forbidden: Clave de sincronización inválida")

    db = SessionLocal()
    try:
        current = ConfigRepository.get_cached()
        if current.get("authToken") == payload.authToken:
            return {"status": "unchanged"}
            
        repo = ConfigRepository(db)
        repo.set_key("authToken", payload.authToken)
        logger.info(f"Sincronización exitosa: Token actualizado en DB")
        return {"status": "success"}
    finally:
        db.close()
