from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List
import asyncio

from src.infrastructure.repositories.config_repository import ConfigRepository
from src.jt_api.client import JTClient
from src.services.settlement_service import SettlementService

router = APIRouter(prefix="/api/settlements", tags=["Settlements"])

class RatePayload(BaseModel):
    account_code: str
    account_name: str
    rate_per_delivery: float

class SettlementGeneratePayload(BaseModel):
    account_code: str
    account_name: str
    network_code: str
    start_time: str
    end_time: str
    deduction_per_issue: float = 0
    rate_per_delivery: float | None = None

class SettlementStatusPayload(BaseModel):
    status: str

@router.post("/rate")
async def set_messenger_rate(payload: RatePayload):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository.get_cached()))
            return service.set_rate(payload.account_code, payload.account_name, payload.rate_per_delivery)
        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/rate")
async def get_messenger_rate(account_code: str):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository.get_cached()))
            return service.get_rate(account_code)
        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/generate")
async def generate_settlement(payload: SettlementGeneratePayload):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository.get_cached()))
            return service.generate_settlement(
                account_code=payload.account_code,
                account_name=payload.account_name,
                network_code=payload.network_code,
                start_time=payload.start_time,
                end_time=payload.end_time,
                deduction_per_issue=payload.deduction_per_issue,
                rate_per_delivery_override=payload.rate_per_delivery,
            )
        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/")
async def list_settlements(account_code: Optional[str] = None, limit: int = 20):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository.get_cached()))
            return service.list_settlements(account_code=account_code, limit=limit)
        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/{settlement_id}")
async def get_settlement(settlement_id: int):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository.get_cached()))
            return service.get_settlement(settlement_id)
        data = await asyncio.to_thread(_run)
        if not data:
            raise HTTPException(status_code=404, detail="Liquidación no encontrada")
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/{settlement_id}/status")
async def update_settlement_status(settlement_id: int, payload: SettlementStatusPayload):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository.get_cached()))
            ok = service.update_status(settlement_id, payload.status)
            if not ok:
                raise HTTPException(status_code=404, detail="Liquidación no encontrada")
            return True
        await asyncio.to_thread(_run)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/{settlement_id}")
async def delete_settlement(settlement_id: int):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository.get_cached()))
            ok = service.delete_settlement(settlement_id)
            if not ok:
                raise HTTPException(status_code=404, detail="Liquidación no encontrada")
            return True
        await asyncio.to_thread(_run)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
