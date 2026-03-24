import asyncio
import io
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.jt_api.client import JTClient
from src.services.temu_alert_service import TemuAlertService
from src.services.temu_prediction_service import temu_prediction_service
from src.services.kpi_service import KPIService
from src.infrastructure.repositories.kpi_repository import KPIRepository
from src.infrastructure.database.deps import get_db
from src.infrastructure.database.connection import SessionLocal
from src.services.waybill_network_service import WaybillNetworkService, WaybillFilterCriteria, WaybillDTO
from src.services.global_search_service import GlobalSearchService
from src.domain.exceptions import InvalidFilterCriteriaError, ExternalAPIError
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api", tags=["Dashboard & Core"])




@router.get("/search")
async def global_search(q: str, limit: int = 6) -> dict:
    query = (q or "").strip()
    if len(query) < 2:
        return {"waybills": [], "messengers": [], "novedades": []}

    max_items = max(1, min(limit, 20))
    config = ConfigRepository.get_cached()
    client = JTClient(config=config)
    service = GlobalSearchService(jt_client=client, max_items=max_items)

    try:
        return await asyncio.to_thread(service.search, query)
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
) -> WaybillNetworkService:
    return WaybillNetworkService(client, repo)

@router.post("/network/waybills")
async def get_network_waybills(
    criteria: WaybillFilterCriteria,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    service: WaybillNetworkService = Depends(get_waybill_network_service)
) -> dict:
    try:
        response = await asyncio.to_thread(service.get_network_waybills, criteria, background_tasks)
        return response.model_dump(by_alias=True, exclude_none=True)
    except InvalidFilterCriteriaError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ExternalAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Error upstream J&T: {exc}")
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.post("/network/waybills/details")
async def get_waybill_cell_details(
    criteria: WaybillFilterCriteria,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    service: WaybillNetworkService = Depends(get_waybill_network_service)
) -> list:
    """Returns a flat list of WaybillDTOs for a single staff × date cell.
    Consumed by the detail modal — no matrix wrapping."""
    try:
        records = await asyncio.to_thread(service.get_cell_details, criteria, background_tasks)
        return [r.model_dump(by_alias=True) for r in records]
    except InvalidFilterCriteriaError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ExternalAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Error upstream J&T: {exc}")
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno del servidor")

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
