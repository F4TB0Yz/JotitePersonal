from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import io
import zipfile
import re
import asyncio
import concurrent.futures
from urllib.parse import urlparse
from datetime import datetime

from src.infrastructure.repositories.config_repository import ConfigRepository
from src.jt_api.client import JTClient
from src.services.report_service import ReportService

router = APIRouter(prefix="/api/waybills", tags=["Waybills"])

class WaybillList(BaseModel):
    waybills: List[str]

class WaybillReprintPayload(BaseModel):
    waybill_ids: List[str]
    bill_type: str = "small"

_PHOTO_ALLOWED_DOMAINS = frozenset({
    "pro-jmsco-file.jtexpress.co",
    "jmsco-file.jtexpress.co",
})


@router.post("/addresses")
async def get_waybills_addresses(payload: WaybillList):
    """
    Recibe una lista de números de guía y devuelve la dirección de destino.
    Se ejecuta en paralelo para ser más rápido.
    """
    if not payload.waybills:
        return {}

    def _fetch_all():
        config = ConfigRepository.get_cached(); client = JTClient(config=config)
        results = {}

        def fetch_address(wb):
            try:
                resp = client.get_order_detail(wb)
                if resp.get("code") == 1 and "data" in resp:
                    details = resp["data"].get("details", {})
                    return wb, details.get("receiverDetailedAddress", "Desconocida")
                return wb, "Desconocida"
            except Exception:
                return wb, "Desconocida"

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_address, wb): wb for wb in payload.waybills}
            for future in concurrent.futures.as_completed(futures):
                wb, address = future.result()
                results[wb] = address

        return results

    return await asyncio.to_thread(_fetch_all)


@router.post("/phones")
async def get_waybills_phones(payload: WaybillList):
    if not payload.waybills:
        return {}

    def _fetch():
        config = ConfigRepository.get_cached(); client = JTClient(config=config)
        return client.get_waybill_receiver_phone(payload.waybills)

    try:
        response = await asyncio.to_thread(_fetch)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if response.get("code") != 1:
        raise HTTPException(status_code=500, detail=response.get("msg", "No se pudieron consultar los teléfonos."))

    data = response.get("data") or []
    phones = {}
    unresolved = []
    for item in data:
        wb = item.get("waybillNo")
        phone = item.get("receiverMobilePhone") or item.get("receiverTelphone")
        if wb:
            phones[wb] = phone
        else:
            unresolved.append(item)

    remaining_wbs = [wb for wb in payload.waybills if wb not in phones]
    for wb, item in zip(remaining_wbs, unresolved):
        phones[wb] = item.get("receiverMobilePhone") or item.get("receiverTelphone")

    for wb in payload.waybills:
        phones.setdefault(wb, None)

    return phones


@router.post("/details")
async def get_waybills_details(payload: WaybillList):
    """
    Recibe una lista de guías y devuelve información enriquecida del destinatario
    (nombre, ciudad, dirección, estado, etc.) consultando el detalle oficial.
    """
    if not payload.waybills:
        return {}

    def _fetch_all():
        config = ConfigRepository.get_cached(); client = JTClient(config=config)
        results = {}

        def extract_detail(wb):
            from src.infrastructure.database.connection import SessionLocal
            from src.infrastructure.repositories.returns_repository import ReturnsRepository
            from src.infrastructure.repositories.novedades_repository import NovedadesRepository

            db_worker = SessionLocal()
            try:
                service = ReportService(
                    client, 
                    returns_repo=ReturnsRepository(db_worker), 
                    novedades_repo=NovedadesRepository(db_worker)
                )
                row = service.get_consolidated_data(wb)
                return wb, {
                    "waybillNo": wb,
                    "receiverName": row.receiver,
                    "receiverCity": row.city,
                    "receiverAddress": row.address,
                    "receiverPhone": row.phone,
                    "status": row.status,
                    "weight": row.weight,
                    "lastEventTime": row.delivery_time if row.is_delivered else "",
                    "signerName": row.signer_name
                }
            except Exception:
                return wb, None
            finally:
                db_worker.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(extract_detail, wb): wb for wb in payload.waybills}
            for future in concurrent.futures.as_completed(futures):
                wb, detail = future.result()
                results[wb] = detail

        return results

    return await asyncio.to_thread(_fetch_all)


@router.post("/intelligence-export")
async def get_waybills_intelligence_export(payload: WaybillList):
    """
    Devuelve un payload enriquecido por guía para análisis externo,
    incluyendo detalle oficial y la línea de tiempo completa de movimientos.
    """
    unique_waybills = []
    seen = set()
    for raw_waybill in payload.waybills:
        normalized = (raw_waybill or "").strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_waybills.append(normalized)

    if not unique_waybills:
        return {"generatedAt": datetime.utcnow().isoformat(), "results": {}}

    def _fetch_all():
        config = ConfigRepository.get_cached(); client = JTClient(config=config)
        from src.infrastructure.database.connection import SessionLocal
        results = {}

        def extract_export_payload(waybill_no: str):
            payload_item = {
                "waybillNo": waybill_no,
                "detail": None,
                "timeline": [],
                "timelineSummary": {
                    "eventCount": 0,
                    "lastEventTime": "",
                    "lastStatus": "",
                },
                "raw": {
                    "details": None,
                    "orderInfo": None,
                },
                "errors": [],
            }

            try:
                detail_response = client.get_order_detail(waybill_no)
                if detail_response.get("code") == 1:
                    data = detail_response.get("data", {}) or {}
                    payload_item["raw"] = {
                        "details": data.get("details", {}) or {},
                        "orderInfo": data.get("orderInfo") or data.get("waybillInfo") or {},
                    }

                    from src.infrastructure.repositories.returns_repository import ReturnsRepository
                    from src.infrastructure.repositories.novedades_repository import NovedadesRepository
                    db_worker = SessionLocal()
                    try:
                        service = ReportService(client, ReturnsRepository(db_worker), NovedadesRepository(db_worker))
                        row = service.get_consolidated_data(waybill_no)
                        payload_item["detail"] = {
                            "waybillNo": waybill_no,
                            "receiverName": row.receiver,
                            "receiverCity": row.city,
                            "receiverAddress": row.address,
                            "receiverPhone": row.phone,
                            "status": row.status,
                            "weight": row.weight,
                            "signTime": row.delivery_time if row.is_delivered else ""
                        }
                    finally:
                        db_worker.close()
                else:
                    payload_item["errors"].append(
                        detail_response.get("msg") or "No se pudo consultar el detalle oficial."
                    )
            except Exception as exc:
                payload_item["errors"].append(f"detail: {exc}")

            db_worker = SessionLocal()
            try:
                from src.infrastructure.repositories.returns_repository import ReturnsRepository
                from src.infrastructure.repositories.novedades_repository import NovedadesRepository
                from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
                worker_report_service = ReportService(
                    client, 
                    returns_repo=ReturnsRepository(db_worker), 
                    novedades_repo=NovedadesRepository(db_worker), 
                    tracking_repo=TrackingEventRepository(db_worker)
                )
                events = worker_report_service.get_timeline(waybill_no, max_age_minutes=60)
                timeline = [
                    {
                        "time": event.time,
                        "typeName": event.type_name,
                        "networkName": event.network_name,
                        "staffName": event.staff_name,
                        "staffContact": event.staff_contact,
                        "status": event.status,
                        "content": event.content,
                    }
                    for event in events
                ]
                payload_item["timeline"] = timeline
                payload_item["timelineSummary"] = {
                    "eventCount": len(timeline),
                    "lastEventTime": timeline[0]["time"] if timeline else "",
                    "lastStatus": (
                        timeline[0].get("status")
                        or timeline[0].get("typeName")
                        or ""
                    ) if timeline else "",
                }
            except Exception as exc:
                payload_item["errors"].append(f"timeline: {exc}")
            finally:
                db_worker.close()

            return waybill_no, payload_item

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(extract_export_payload, wb): wb
                for wb in unique_waybills
            }
            for future in concurrent.futures.as_completed(futures):
                waybill_no, item = future.result()
                results[waybill_no] = item

        return {
            "generatedAt": datetime.utcnow().isoformat(),
            "results": results,
        }

    return await asyncio.to_thread(_fetch_all)

@router.post("/export-csv")
async def export_waybills_csv(payload: List[dict]):
    """
    Recibe los datos consolidados del frontend y los devuelve como un CSV streameado.
    """
    if not payload:
        raise HTTPException(status_code=400, detail="No hay datos para exportar.")
    try:
        from src.utils.exporter import export_to_csv_stream
        csv_bytes = export_to_csv_stream(payload)
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=reporte_consolidado.csv"}
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{waybill_no}/timeline")
async def get_waybill_timeline(waybill_no: str, max_age_minutes: int = 30):
    normalized_wb = (waybill_no or "").strip().upper()
    if not normalized_wb:
        raise HTTPException(status_code=400, detail="Waybill requerido")

    try:
        def _fetch():
            config = ConfigRepository.get_cached(); client = JTClient(config=config)
            from src.infrastructure.database.connection import SessionLocal
            from src.infrastructure.repositories.returns_repository import ReturnsRepository
            from src.infrastructure.repositories.novedades_repository import NovedadesRepository
            with SessionLocal() as db_session:
                returns_repo = ReturnsRepository(db_session)
                novedades_repo = NovedadesRepository(db_session)
                service = ReportService(client, returns_repo, novedades_repo)
                return service.get_timeline(normalized_wb, max_age_minutes=max_age_minutes)
        events = await asyncio.to_thread(_fetch)

        current_status = events[0].status if events else "Desconocido"
        response_events = [
            {
                "time": event.time,
                "type_name": event.type_name,
                "network_name": event.network_name,
                "staff_name": event.staff_name,
                "staff_contact": event.staff_contact,
                "status": event.status,
                "content": event.content,
            }
            for event in events
        ]
        return {
            "waybill_no": normalized_wb,
            "current_status": current_status,
            "events": response_events,
        }
    except Exception as exc:
        return {
            "waybill_no": normalized_wb,
            "current_status": "Desconocido",
            "events": [],
            "error": str(exc),
        }


@router.post("/reprint")
async def reprint_waybills(payload: WaybillReprintPayload):
    try:
        def _fetch():
            config = ConfigRepository.get_cached(); client = JTClient(config=config)
            return client.reprint_waybills(payload.waybill_ids, payload.bill_type)

        response = await asyncio.to_thread(_fetch)

        if response.get("code") != 1:
            message = response.get("msg") or "No se pudo generar el PDF de reimpresión"
            raise HTTPException(status_code=400, detail=message)

        data = response.get("data") or {}
        pdf_url = data.get("centrePrintUrl") or data.get("centerPrintUrl")
        if not pdf_url:
            raise HTTPException(status_code=502, detail="La API de J&T no devolvió URL de PDF")

        return {
            "success": True,
            "data": {
                "pdf_url": pdf_url,
                "bill_type": payload.bill_type,
                "waybill_ids": payload.waybill_ids,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{waybill_no}/photos")
async def get_waybill_photos(waybill_no: str):
    normalized_wb = (waybill_no or "").strip().upper()
    if not normalized_wb:
        raise HTTPException(status_code=400, detail="Waybill requerido")

    try:
        def _fetch():
            config = ConfigRepository.get_cached(); client = JTClient(config=config)
            from src.infrastructure.database.connection import SessionLocal
            from src.infrastructure.repositories.returns_repository import ReturnsRepository
            from src.infrastructure.repositories.novedades_repository import NovedadesRepository
            
            scan_time = None
            scan_by_code = None

            db_worker = SessionLocal()
            try:
                service = ReportService(client, ReturnsRepository(db_worker), NovedadesRepository(db_worker))
                events = service.get_timeline(normalized_wb)
                for event in events:
                    if service._is_signed_event(event):
                        scan_time = event.time
                        scan_by_code = event.scan_by_code
                        break
            finally:
                db_worker.close()

            if not scan_time:
                return {"waybill_no": normalized_wb, "photos": [], "error": "No se encontró evento de firma/entrega"}

            formatted_scan_time = scan_time.replace("T", " ") if scan_time else ""
            photos_resp = client.get_delivery_photos(normalized_wb, formatted_scan_time, scan_by_code or "")

            if photos_resp.get("code") != 1:
                return {
                    "waybill_no": normalized_wb,
                    "photos": [],
                    "error": photos_resp.get("msg", "Error al consultar fotos"),
                }

            return {
                "waybill_no": normalized_wb,
                "photos": photos_resp.get("data") or [],
                "scan_time": scan_time,
            }

        return await asyncio.to_thread(_fetch)
    except Exception as exc:
        return {"waybill_no": normalized_wb, "photos": [], "error": str(exc)}


@router.get("/{waybill_no}/photos/download")
async def download_waybill_photos(waybill_no: str):
    import requests as _requests

    normalized_wb = (waybill_no or "").strip().upper()
    if not normalized_wb:
        raise HTTPException(status_code=400, detail="Waybill requerido")

    def _fetch():
        config = ConfigRepository.get_cached(); client = JTClient(config=config)
        from src.infrastructure.database.connection import SessionLocal
        from src.infrastructure.repositories.returns_repository import ReturnsRepository
        from src.infrastructure.repositories.novedades_repository import NovedadesRepository
        
        scan_time = None
        scan_by_code = None

        db_worker = SessionLocal()
        try:
            service = ReportService(client, ReturnsRepository(db_worker), NovedadesRepository(db_worker))
            events = service.get_timeline(normalized_wb)
            for event in events:
                if service._is_signed_event(event):
                    scan_time = event.time
                    scan_by_code = event.scan_by_code
                    break
        finally:
            db_worker.close()

        if not scan_time:
            raise HTTPException(status_code=404, detail="No se encontró evento de firma/entrega")

        formatted_scan_time = scan_time.replace("T", " ") if scan_time else ""
        photos_resp = client.get_delivery_photos(normalized_wb, formatted_scan_time, scan_by_code or "")

        if photos_resp.get("code") != 1:
            raise HTTPException(
                status_code=502,
                detail=photos_resp.get("msg", "Error al consultar fotos"),
            )

        photos = photos_resp.get("data") or []
        if not photos:
            raise HTTPException(status_code=404, detail="No hay fotos disponibles para esta guía")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, url in enumerate(photos, start=1):
                parsed = urlparse(url)
                if parsed.hostname not in _PHOTO_ALLOWED_DOMAINS:
                    continue
                resp = _requests.get(url, timeout=20)
                resp.raise_for_status()
                ext = parsed.path.rsplit(".", 1)[-1] if "." in parsed.path else "jpg"
                zf.writestr(f"{normalized_wb}_foto_{idx}.{ext}", resp.content)

        buf.seek(0)
        return buf

    try:
        buf = await asyncio.to_thread(_fetch)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{normalized_wb}_fotos_entrega.zip"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
