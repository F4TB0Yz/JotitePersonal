import re
import asyncio
import io
import random
import time
from typing import Optional, List
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Body, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.jt_api.client import JTClient
from src.services.temu_alert_service import TemuAlertService
from src.services.temu_prediction_service import temu_prediction_service
from src.services.novedades_service import novedades_service
from src.services.kpi_service import kpi_service

router = APIRouter(prefix="/api", tags=["Dashboard & Core"])

def _auto_heal_stale_waybills(waybills: list[str]):
    if not waybills:
        return
        
    config = ConfigRepository.get_cached()
    client = JTClient(config=config)
    
    with SessionLocal() as db:
        repo = TrackingEventRepository(db)
        from src.models.waybill import TrackingEvent
        
        for wb in waybills:
            if not wb: continue
            try:
                # Vamos a pedirle la realidad actual a J&T
                resp = client.get_order_detail(wb)
                details = resp.get("data", {}).get("details", [])
                if details:
                    events = [
                        TrackingEvent(
                            time=d.get("scanTime"),
                            type_name=d.get("scanTypeName"),
                            network_name=d.get("scanNetworkName"),
                            scan_network_id=d.get("scanNetworkId"),
                            staff_name=d.get("scanByName"),
                            staff_contact="",
                            status=d.get("status"),
                            content=d.get("waybillTrackingContent"),
                            code=d.get("code")
                        ) for d in details
                    ]
                    # Aquí la magia: guardamos los eventos nuevos en tu BD local
                    repo.save_events(wb, events)
                
                # LA CRUDA REALIDAD: Si no pones a dormir el hilo, te banean.
                time.sleep(0.5) 
            except Exception:
                time.sleep(0.5) # Respira también si hay error
                continue

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
            novedades_results = novedades_service.search_novedades(query, limit=max_items)
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

@router.post("/network/waybills")
async def get_network_waybills(req: dict = Body(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    network_code = req.get("networkCode")
    start_time = req.get("startTime")
    end_time = req.get("endTime")
    sign_type = req.get("signType", 0)

    if not all([network_code, start_time, end_time]):
        raise HTTPException(status_code=400, detail="Faltan parámetros requeridos.")

    try:
        def _fetch_network():
            config = ConfigRepository.get_cached()
            client = JTClient(config=config)
            response = client.get_network_signing_detail(
                network_code=network_code,
                start_time=start_time,
                end_time=end_time,
                sign_type=sign_type
            )
            records = response.get("data", {}).get("records", []) or []

            # El filtro de ubicación solo aplica a guías pendientes (signType=0).
            # Las ya firmadas (signType=1) no necesitan esta corrección.
            if not records or sign_type != 0:
                return {"records": records}

            # Extraer números de guía del response.  J&T puede usar distintos
            # nombres de campo según el endpoint; probamos los más comunes.
            waybill_nos: list[str] = [
                r.get("waybillNo") or r.get("billCode") or r.get("orderId") or ""
                for r in records
            ]
            waybill_nos = [wb.strip().upper() for wb in waybill_nos if wb and wb.strip()]

            if not waybill_nos:
                return {"records": records}

            # Consultar la tabla local tracking_events para detectar qué guías
            # tienen evidencia de haber salido físicamente de esta red, usando el network_code (ej. 1009).
            with SessionLocal() as db:
                departed = TrackingEventRepository.get_departed_waybills(
                    db, waybill_nos, current_network_id=network_code
                )

            if not departed:
                # Priorizamos los primeros 10 y luego 5 al azar del resto
                sample_to_heal = waybill_nos[:10]
                if len(waybill_nos) > 10:
                    sample_to_heal += random.sample(waybill_nos[10:], min(5, len(waybill_nos) - 10))
                background_tasks.add_task(_auto_heal_stale_waybills, sample_to_heal)
                return {"records": records}

            filtered = []
            for r in records:
                wb = (r.get("waybillNo") or r.get("billCode") or r.get("orderId") or "").strip().upper()
                if not wb:
                    continue
                
                # 1. Filtro por base de datos local (historial conocido)
                if wb in departed:
                    continue
                
                # 2. Filtro DIRECTO por información en el record de J&T
                # Si el record ya dice que está en otra red o tiene estados terminales
                r_net_id = str(r.get("scanNetworkId") or "")
                r_net_name = str(r.get("scanNetworkName") or "")
                r_status = str(r.get("waybillStatus") or r.get("status") or "")
                r_type = str(r.get("scanTypeName") or "")

                # 3. Filtro específico pedido: Carga y expedición en Cund-Punto6 (1009)
                # Si el estado es "Carga y expedición" y la red es Punto6, se va de la lista de pendientes.
                if "Carga y expedición" in r_type:
                    if r_net_id == "1009" or r_net_id == str(network_code) or "Cund-Punto6" in r_net_name:
                         continue
                
                # 4. Filtro por red de rastro (Si el record indica que ya está físicamente en otra red)
                if r_net_id and network_code and r_net_id != str(network_code):
                    # Si el ID de red no coincide con el buscado, es porque ya se movió.
                    continue
                
                # 5. Filtro por nombre de red (Bogotá suele ser punto de retorno/tránsito superior)
                if ("Bogota" in r_net_name or "Centro" in r_net_name) and "Bogota" not in str(network_code):
                    continue

                # 6. Estados Terminales
                if any(x in r_type or x in r_status for x in ["Entregado", "Devuelto", "Firmado", "Anulado"]):
                    continue

                filtered.append(r)
            
            survivors = [r.get("waybillNo") or r.get("billCode") or r.get("orderId") or "" for r in filtered]
            
            # Curamos los primeros 15 supervivientes y 5 al azar del resto (Acomodado a 20 total)
            sample_survivors = survivors[:15]
            if len(survivors) > 15:
                sample_survivors += random.sample(survivors[15:], min(5, len(survivors) - 15))
            background_tasks.add_task(_auto_heal_stale_waybills, sample_survivors)

            return {"records": filtered, "_filtered_count": len(records) - len(filtered)}

        return await asyncio.to_thread(_fetch_network)
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
            return kpi_service.get_overview(
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
    _PHOTO_ALLOWED_DOMAINS = {"jtexpress.com.co", "jt-express.com.co"}
    parsed = urlparse(url)
    if parsed.hostname not in _PHOTO_ALLOWED_DOMAINS:
        raise HTTPException(status_code=403, detail="Dominio no permitido")
    safe_filename = re.sub(r"[^\w\.\-]", "_", filename)[:80]
    try:
        def _fetch():
            resp = _requests.get(url, timeout=20)
            resp.raise_for_status()
            return resp.content, resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        content, content_type = await asyncio.to_thread(_fetch)
        return StreamingResponse(
            io.BytesIO(content),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
