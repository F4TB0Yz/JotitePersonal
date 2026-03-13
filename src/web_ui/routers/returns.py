from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import os
from datetime import datetime, timedelta

from src.infrastructure.repositories.config_repository import ConfigRepository
from src.jt_api.client import JTClient
from src.services.returns_service import ReturnsService

router = APIRouter(prefix="/api/returns", tags=["Returns"])

# Lock compartido para sincronización, exportado para el loop de main_web
returns_sync_lock = asyncio.Lock()

class ReturnsSyncPayload(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    statuses: List[int] = [1, 2, 3]
    size: int = 50
    max_pages: int = 20

class ReturnPrintUrlPayload(BaseModel):
    waybill_no: str
    template_size: int = 1
    pring_type: int = 1
    printer: int = 0

def _format_returns_datetime(value: str | None, is_end: bool = False) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) == 10:
        suffix = "23:59:59" if is_end else "00:00:00"
        return f"{raw} {suffix}"
    return raw

def _resolve_returns_range(date_from: str | None, date_to: str | None, lookback_days: int = 2) -> tuple[str, str]:
    now = datetime.now()
    default_from = (now - timedelta(days=max(0, lookback_days))).strftime("%Y-%m-%d 00:00:00")
    default_to = now.strftime("%Y-%m-%d 23:59:59")
    return (
        _format_returns_datetime(date_from, is_end=False) or default_from,
        _format_returns_datetime(date_to, is_end=True) or default_to,
    )

def _build_returns_service() -> ReturnsService:
    cfg = ConfigRepository.get_cached()
    apply_network_id = int(os.getenv("RETURNS_APPLY_NETWORK_ID", "1009"))
    return ReturnsService(JTClient(config=cfg), apply_network_id=apply_network_id)

@router.get("/applications")
async def get_return_applications(
    status: int = 1,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current: int = 1,
    size: int = 20,
    save_snapshot: bool = True,
):
    if status not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="status debe ser 1 (En revisión), 2 (Aprobada) o 3 (Rechazada)")

    start_time, end_time = _resolve_returns_range(date_from, date_to)

    try:
        def _run():
            service = _build_returns_service()
            return service.fetch_applications(
                status=status,
                apply_time_from=start_time,
                apply_time_to=end_time,
                current=current,
                size=size,
                save_snapshot=save_snapshot,
            )

        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/snapshots")
async def get_return_snapshots(
    status: Optional[int] = None,
    waybill_no: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    if status is not None and status not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="status debe ser 1 (En revisión), 2 (Aprobada) o 3 (Rechazada)")

    start_time = _format_returns_datetime(date_from, is_end=False)
    end_time = _format_returns_datetime(date_to, is_end=True)

    try:
        def _run():
            service = _build_returns_service()
            return service.list_snapshots(
                status=status,
                waybill_no=waybill_no,
                date_from=start_time or None,
                date_to=end_time or None,
                limit=limit,
                offset=offset,
            )

        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/sync")
async def sync_return_snapshots(payload: ReturnsSyncPayload):
    statuses = [status for status in (payload.statuses or [1, 2, 3]) if status in (1, 2, 3)]
    if not statuses:
        raise HTTPException(status_code=400, detail="Debe incluir al menos un status válido (1, 2 o 3)")

    start_time, end_time = _resolve_returns_range(payload.date_from, payload.date_to)

    try:
        async with returns_sync_lock:
            def _run():
                service = _build_returns_service()
                return service.sync_statuses(
                    apply_time_from=start_time,
                    apply_time_to=end_time,
                    statuses=statuses,
                    size=payload.size,
                    max_pages=payload.max_pages,
                )

            data = await asyncio.to_thread(_run)

        return {"success": True, "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/printable")
async def get_return_printable(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current: int = 1,
    size: int = 20,
    pring_flag: int = 0,
    printer: int = 0,
    template_size: int = 1,
    pring_type: int = 1,
):
    start_time, end_time = _resolve_returns_range(date_from, date_to)

    try:
        def _run():
            service = _build_returns_service()
            return service.fetch_printable_list(
                apply_time_from=start_time,
                apply_time_to=end_time,
                current=current,
                size=size,
                pring_flag=pring_flag,
                printer=printer,
                template_size=template_size,
                pring_type=pring_type,
            )

        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/print-url")
async def get_return_print_url(payload: ReturnPrintUrlPayload):
    try:
        def _run():
            service = _build_returns_service()
            return service.get_print_waybill_url(
                waybill_no=payload.waybill_no,
                template_size=payload.template_size,
                pring_type=payload.pring_type,
                printer=payload.printer,
            )

        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
