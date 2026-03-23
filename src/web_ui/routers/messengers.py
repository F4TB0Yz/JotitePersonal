from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from datetime import datetime, timedelta

from src.infrastructure.repositories.config_repository import ConfigRepository
from src.jt_api.client import JTClient

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

@router.get("/contact")
async def get_messenger_contact(name: str, network_code: str | None = "1009", waybill: str | None = None):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Nombre requerido")

    def _fetch_contact():
        config = ConfigRepository.get_cached(); client = JTClient(config=config)
        normalized = name.strip().lower()
        response = client.search_messengers(name.strip(), network_id=network_code)
        data = response.get("data") or {}
        records = data.get("records") if isinstance(data, dict) else data
        if records and not isinstance(records, list):
            records = [records]

        best_match = None
        if records:
            for record in records:
                account_name = (record.get("accountName") or "").strip().lower()
                if account_name == normalized:
                    best_match = record
                    break
            if not best_match:
                best_match = records[0]

        phone_fields = [
            "accountPhone",
            "accountTel",
            "accountMobile",
            "contactPhone",
            "contactTel",
            "contactMobile",
            "phone",
            "mobilePhone",
            "telPhone"
        ]
        phone_value = None
        if best_match:
            for field in phone_fields:
                candidate = best_match.get(field)
                if candidate:
                    phone_value = candidate
                    break

        tracking_phone = None
        tracking_name = None
        
        # Note: account_code usage here might be problematic if not defined, 
        # but I'm keeping the logic as requested without altering it.
        # It seems it was potentially relying on a global or was a bug.
        # Check if best_match exists to safely access accountCode if needed.
        account_code = best_match.get("accountCode") if best_match else None
        
        if (not phone_value) and (not waybill or not waybill.strip()) and account_code:
            try:
                today_dt = datetime.now()
                end_str = today_dt.strftime("%Y-%m-%d 23:59:59")
                start_str = (today_dt - timedelta(days=3)).strftime("%Y-%m-%d 00:00:00")
                net_code = best_match.get("customerNetworkCode") if best_match else (network_code or "1025006")
                wb_resp = client.get_messenger_waybills_detail(account_code, net_code, start_str, end_str, current=1, size=1)
                
                if isinstance(wb_resp, dict) and wb_resp.get("code") == 1:
                    wb_records = wb_resp.get("data", {}).get("records", [])
                    if wb_records and isinstance(wb_records, list) and len(wb_records) > 0:
                        waybill = wb_records[0].get("waybillNo")
            except Exception as e:
                print(f"Error auto-fetching waybill for contact: {e}")

        if (not phone_value) and waybill and waybill.strip():
            try:
                tracking = client.get_tracking_list(waybill.strip())
                data = tracking.get("data") or []
                prioritized = None
                fallback = None
                for entry in data:
                    for detail in entry.get("details", []):
                        contact = detail.get("staffContact")
                        if not contact:
                            continue
                        staff_name = (detail.get("staffName") or "").strip()
                        if staff_name and staff_name.lower() == normalized:
                            prioritized = (contact, staff_name)
                            break
                        if not fallback:
                            fallback = (contact, staff_name)
                    if prioritized:
                        break
                chosen = prioritized or fallback
                if chosen:
                    tracking_phone, tracking_name = chosen
            except Exception as tracking_error:
                print(f"Error consultando tracking para teléfono: {tracking_error}")

        final_phone = phone_value or tracking_phone
        if tracking_name:
            final_name = tracking_name
        elif best_match:
            final_name = best_match.get("accountName") or name.strip()
        else:
            final_name = name.strip()
        
        network_name = best_match.get("customerNetworkName") if best_match else None

        if not final_phone and not best_match:
            raise HTTPException(status_code=404, detail="Mensajero no encontrado")

        return {
            "name": final_name,
            "accountCode": account_code,
            "networkName": network_name,
            "phone": final_phone
        }

    try:
        return await asyncio.to_thread(_fetch_contact)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

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
