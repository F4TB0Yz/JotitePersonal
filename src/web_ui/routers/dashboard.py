import re
import asyncio
import io
import random
import time
from typing import Optional, List
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Body, Request, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.jt_api.client import JTClient
from src.services.temu_alert_service import TemuAlertService
from src.services.temu_prediction_service import temu_prediction_service
from src.services.novedades_service import NovedadesService
from src.services.kpi_service import KPIService
from src.infrastructure.repositories.novedades_repository import NovedadesRepository
from src.infrastructure.repositories.kpi_repository import KPIRepository
from src.infrastructure.database.deps import get_db
from src.services.waybill_network_service import WaybillNetworkService, WaybillFilterCriteria
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api", tags=["Dashboard & Core"])



def _normalize_waybill_record(waybill_no: str, details: dict) -> dict:
    return {
        "waybill_no": waybill_no,
        "receiver": details.get("receiverName") or details.get("receiver") or "N/A",
        "city": details.get("receiverCity") or details.get("city") or "N/A",
        "address": details.get("receiverDetailedAddress") or details.get("address") or "N/A",
        "sender": details.get("senderName") or details.get("sender") or "N/A",
        "order_source": details.get("orderSource") or "N/A",
    }

@router.get("/search")
async def global_search(q: str, limit: int = 6):
    query = (q or "").strip()
    if len(query) < 2:
        return {"waybills": [], "messengers": [], "novedades": []}

    max_items = max(1, min(limit, 20))

    def _search():
        waybill_results = []
        messenger_results = []
        novedades_results = []

        config = ConfigRepository.get_cached(); client = JTClient(config=config)

        maybe_waybill = bool(re.fullmatch(r"[A-Za-z0-9\-]{6,32}", query))
        if maybe_waybill:
            try:
                waybill_no = query.upper()
                detail_resp = client.get_order_detail(waybill_no)
                if detail_resp.get("code") == 1:
                    details = detail_resp.get("data", {}).get("details", {})
                    if details:
                        waybill_results.append(_normalize_waybill_record(waybill_no, details))
            except Exception:
                pass

        try:
            messenger_resp = client.search_messengers(query)
            if messenger_resp.get("code") == 1 and "data" in messenger_resp:
                data = messenger_resp.get("data")
                records = data.get("records", []) if isinstance(data, dict) else (data or [])
                messenger_results = records[:max_items]
        except Exception:
            pass

        try:
            with SessionLocal() as db:
                novedades_repo = NovedadesRepository(db)
                novedades_svc = NovedadesService(novedades_repo)
                novedades_results = novedades_svc.search_novedades(query, limit=max_items)
        except Exception:
            pass

        return {
            "waybills": waybill_results[:max_items],
            "messengers": messenger_results[:max_items],
            "novedades": novedades_results[:max_items],
        }

    try:
        return await asyncio.to_thread(_search)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

def get_jt_client() -> JTClient:
    config = ConfigRepository.get_cached()
    return JTClient(config=config)

def get_tracking_repository(db: Session = Depends(get_db)) -> TrackingEventRepository:
    return TrackingEventRepository(db)

def get_waybill_network_service(
    client: JTClient = Depends(get_jt_client),
    repo: TrackingEventRepository = Depends(get_tracking_repository),
    db: Session = Depends(get_db)
) -> WaybillNetworkService:
    return WaybillNetworkService(client, repo, db)

@router.post("/network/waybills")
async def get_network_waybills(
    req: dict = Body(...), 
    background_tasks: BackgroundTasks = BackgroundTasks(),
    service: WaybillNetworkService = Depends(get_waybill_network_service)
):
    try:
        criteria = WaybillFilterCriteria(**req)
    except Exception:
        raise HTTPException(status_code=400, detail="Faltan parámetros requeridos.")

    try:
        response = await asyncio.to_thread(service.get_network_waybills, criteria, background_tasks)
        return response.dict(exclude_none=True)
    except Exception as e:
        return {"records": [], "error": str(e)}

@router.get("/alerts/temu")
async def get_temu_alerts(
    threshold_hours: float = 96,
    window_hours: float = 12,
    include_overdue: bool = True,
    duty_agent_code: str = "R00001",
    duty_code: str = "1025006",
    manager_code: str = "108108",
    responsible_org_code: str = "1025006",
    dimension_type: int = 2
):
    try:
        def _fetch():
            config = ConfigRepository.get_cached(); client = JTClient(config=config)
            service = TemuAlertService(client)
            return service.build_alert_report(
                threshold_hours=threshold_hours,
                window_hours=window_hours,
                include_overdue=include_overdue,
                duty_agent_code=duty_agent_code,
                duty_code=duty_code,
                manager_code=manager_code,
                responsible_org_code=responsible_org_code,
                dimension_type=dimension_type
            )
        return await asyncio.to_thread(_fetch)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/alerts/temu/predictions")
async def get_temu_predictions(limit: int = 80):
    try:
        return {
            "items": temu_prediction_service.get_recent_predictions(limit=limit),
            "limit": max(1, min(limit, 200)),
            "mode": "predict-72-to-96",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/kpis/overview")
async def get_kpis_overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    ranking_limit: int = 10,
):
    try:
        def _run():
            with SessionLocal() as db:
                repo = KPIRepository(db)
                svc = KPIService(repo)
                return svc.get_overview(
                    start_date=start_date,
                    end_date=end_date,
                    ranking_limit=ranking_limit,
                )
        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/photos/proxy")
async def proxy_photo(url: str, filename: str = "foto.jpeg"):
    import requests as _requests
    from fastapi.responses import StreamingResponse
    
    # Dominios permitidos (Consolidado de waybills.py y dashboard.py)
    _ALLOWED = {
        "jtexpress.com.co", 
        "jt-express.com.co",
        "pro-jmsco-file.jtexpress.co",
        "jmsco-file.jtexpress.co"
    }
    
    parsed = urlparse(url)
    if parsed.hostname not in _ALLOWED:
        raise HTTPException(status_code=403, detail=f"Dominio '{parsed.hostname}' no permitido para descarga directa.")

    safe_filename = re.sub(r"[^\w\.\-]", "_", filename)[:80]
    if not safe_filename.lower().endswith(('.jpg', '.jpeg', '.png')):
         safe_filename += ".jpeg"

    try:
        def _fetch():
            resp = _requests.get(url, timeout=20)
            resp.raise_for_status()
            # Detectar el tipo de contenido real o usar jpeg por defecto
            ctype = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            if "image" not in ctype:
                ctype = "image/jpeg"
            return resp.content, ctype

        content, content_type = await asyncio.to_thread(_fetch)
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Cache-Control": "max-age=3600"
            },
        )
    except Exception as exc:
        # Si falla el fetch externo, propagamos un 502 (Bad Gateway) con detalle
        raise HTTPException(status_code=502, detail=f"Error al obtener imagen remota: {str(exc)}")
