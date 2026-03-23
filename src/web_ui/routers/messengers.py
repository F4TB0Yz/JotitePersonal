from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from datetime import datetime, timedelta

from src.infrastructure.repositories.config_repository import ConfigRepository
from src.jt_api.client import JTClient
from src.domain.messenger import MessengerContact, MessengerNotFoundException, JTClientIntegrationException
from src.services.get_messenger_contact_use_case import GetMessengerContactUseCase
from src.infrastructure.providers.jt_messenger_provider import JTMessengerProvider

router = APIRouter(prefix="/api/messengers", tags=["Messengers"])

class MessengerItem(BaseModel):
    accountCode: str
    networkCode: str
    accountName: str

class BulkMetricsRequest(BaseModel):
    messengers: List[MessengerItem]
    startTime: str
    endTime: str

@router.get("/search")
async def search_messengers(q: str):
    if not q or len(q) < 2:
        return []
    try:
        def _search():
            config = ConfigRepository.get_cached(); client = JTClient(config=config)
            return client.search_messengers(q)

        response = await asyncio.to_thread(_search)
        if response.get("code") == 1 and "data" in response:
            return response["data"].get("records", []) if "records" in response["data"] else response["data"]
        return []
    except Exception as e:
        print(f"Error buscando mensajeros: {e}")
        return []

def get_messenger_use_case() -> GetMessengerContactUseCase:
    provider = JTMessengerProvider()
    return GetMessengerContactUseCase(provider)

@router.get("/contact", response_model=MessengerContact)
async def get_messenger_contact(
    name: str, 
    network_code: str | None = "1009", 
    waybill: str | None = None,
    use_case: GetMessengerContactUseCase = Depends(get_messenger_use_case)
):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Nombre requerido")

    try:
        return await asyncio.to_thread(use_case.execute, name, network_code, waybill)
    except MessengerNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (JTClientIntegrationException, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")

@router.get("/metrics")
async def get_messenger_metrics(account_code: str, network_code: str, start_time: str, end_time: str):
    if not account_code or not network_code or not start_time or not end_time:
        return {"error": "Missing parameters"}
    try:
        def _fetch():
            config = ConfigRepository.get_cached(); client = JTClient(config=config)
            detail = client.get_messenger_metrics(account_code, network_code, start_time, end_time)
            summary = client.get_messenger_metrics_sum(account_code, network_code, start_time, end_time)
            return {
                "detail": detail.get("data", {}).get("records", []) if detail.get("code") == 1 else [],
                "summary": summary.get("data", {}).get("records", []) if summary.get("code") == 1 else []
            }
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        print(f"Error obteniendo métricas de mensajero: {e}")
        return {"error": str(e)}

@router.get("/waybills")
async def get_messenger_waybills(account_code: str, network_code: str, start_time: str, end_time: str):
    if not account_code or not network_code or not start_time or not end_time:
        return {"error": "Missing parameters"}
    try:
        def _fetch():
            config = ConfigRepository.get_cached(); client = JTClient(config=config)
            return client.get_all_messenger_waybills_detail(account_code, network_code, start_time, end_time)
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        print(f"Error obteniendo paquetes de mensajero: {e}")
        return {"error": str(e)}

@router.post("/bulk-metrics")
async def get_bulk_messenger_metrics(payload: BulkMetricsRequest):
    if not payload.messengers or not payload.startTime or not payload.endTime:
        return {"error": "Missing parameters"}
    if len(payload.messengers) > 30:
        raise HTTPException(status_code=400, detail="Máximo 30 mensajeros por consulta")

    async def _fetch_one(m: MessengerItem):
        try:
            def _call():
                config = ConfigRepository.get_cached(); client = JTClient(config=config)
                response = client.get_messenger_metrics_sum(
                    m.accountCode, m.networkCode, payload.startTime, payload.endTime
                )
                records = []
                if response.get("code") == 1:
                    records = response.get("data", {}).get("records", [])
                if records:
                    r = records[0]
                    dispatch = r.get("dispatchTotal", 0) or 0
                    sign = r.get("signTotal", 0) or 0
                    nosign = r.get("nosignTotal", 0) or 0
                    eff = f"{(sign / dispatch * 100):.1f}%" if dispatch else "0%"
                    return {
                        "accountCode": m.accountCode,
                        "accountName": m.accountName,
                        "dispatchTotal": dispatch,
                        "signTotal": sign,
                        "nosignTotal": nosign,
                        "effectiveness": eff,
                        "error": None
                    }
                return {
                    "accountCode": m.accountCode,
                    "accountName": m.accountName,
                    "dispatchTotal": 0, "signTotal": 0, "nosignTotal": 0,
                    "effectiveness": "0%", "error": None
                }
            return await asyncio.to_thread(_call)
        except Exception as e:
            return {
                "accountCode": m.accountCode,
                "accountName": m.accountName,
                "dispatchTotal": 0, "signTotal": 0, "nosignTotal": 0,
                "effectiveness": "-", "error": str(e)
            }

    results = await asyncio.gather(*[_fetch_one(m) for m in payload.messengers])
    return {"results": list(results)}

@router.get("/daily-report")
async def get_messengers_daily_report(
    date: str = None,
    start_date: str = None,
    end_date: str = None,
    network_code: str = "1025006",
    finance_code: str = "R00001",
):
    resolved_start = start_date or date
    resolved_end = end_date or date

    if not resolved_start or not resolved_end:
        raise HTTPException(status_code=400, detail="Se requiere 'date' o 'start_date'/'end_date'")
    try:
        datetime.strptime(resolved_start, "%Y-%m-%d")
        datetime.strptime(resolved_end, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")

    start_time = f"{resolved_start} 00:00:00"
    end_time = f"{resolved_end} 23:59:59"

    def _fetch():
        config = ConfigRepository.get_cached()
        client = JTClient(config=config)
        return client.get_network_staff_daily(
            network_code=network_code,
            start_time=start_time,
            end_time=end_time,
            finance_code=finance_code,
        )

    try:
        records = await asyncio.to_thread(_fetch)
        return {"records": records, "date": resolved_start, "endDate": resolved_end, "total": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
