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

def _find_signing_event(tracking_data: list) -> tuple[str | None, str | None]:
    """Retorna (scanTime, scanByCode) del primer evento de firma/entrega.
    Usa code==100 como detección principal (language-agnostic).
    """
    for item in (tracking_data[0].get("details") or [] if tracking_data else []):
        scan_by = (
            item.get("scanByCode")
            or item.get("staffCode")
            or item.get("scanBy")
        )
        code = item.get("code")
        status = (item.get("status") or "").lower()
        type_name = (item.get("scanTypeName") or "").lower()
        if scan_by and (
            code == 100
            or "firmado" in status
            or "签收" in (item.get("status") or "")
            or "signing" in type_name
            or "firmado" in type_name
        ):
            return item.get("scanTime"), scan_by
    return None, None

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
            try:
                resp = client.get_order_detail(wb)
                if resp.get("code") != 1:
                    return wb, None
                data = resp.get("data", {})
                details = data.get("details", {}) or {}
                order_info = data.get("orderInfo") or data.get("waybillInfo") or {}

                receiver_name = (
                    details.get("receiverName")
                    or order_info.get("receiverName")
                    or details.get("receiver")
                )
                receiver_city = (
                    details.get("receiverCityName")
                    or order_info.get("receiverCityName")
                    or details.get("receiverCity")
                )
                receiver_address = (
                    details.get("receiverDetailedAddress")
                    or details.get("receiverAddress")
                    or order_info.get("receiverDetailedAddress")
                )
                status = (
                    details.get("waybillStatusName")
                    or details.get("statusName")
                    or details.get("status")
                    or order_info.get("waybillStatusName")
                )
                receiver_phone = (
                    details.get("receiverPhone")
                    or order_info.get("receiverPhone")
                    or details.get("consigneePhone")
                )

                sign_time = details.get("signTime") or order_info.get("signTime") or ""
                signer_name = ""

                # Only call tracking API for packages that appear delivered — no-op for in-transit
                status_lower = (status or "").lower()
                if "firmado" in status_lower or "entregado" in status_lower or "签收" in (status or ""):
                    try:
                        tracking_resp = client.get_tracking_list(wb)
                        tracking_data = tracking_resp.get("data", [])
                        if tracking_data:
                            tracking_items = tracking_data[0].get("details", [])
                            # First pass: look for a "firmado" event (preferred)
                            for item in tracking_items:
                                scan_type = (item.get("scanTypeName") or "").lower()
                                item_status = (item.get("status") or "")
                                is_signed = (
                                    item.get("code") == 100
                                    or "firmado" in scan_type
                                    or "签收" in item_status
                                    or "firmado" in item_status.lower()
                                )
                                if is_signed:
                                    if not sign_time:
                                        sign_time = item.get("scanTime") or ""
                                    signer_name = (item.get("remark3") or "").strip()
                                    break
                            # Second pass: if still no signer, use the last item with a non-empty remark3
                            if not signer_name:
                                for item in reversed(tracking_items):
                                    candidate = (item.get("remark3") or "").strip()
                                    if candidate:
                                        signer_name = candidate
                                        if not sign_time:
                                            sign_time = item.get("scanTime") or ""
                                        break
                    except Exception:
                        pass

                return wb, {
                    "waybillNo": wb,
                    "receiverName": receiver_name,
                    "receiverCity": receiver_city,
                    "receiverAddress": receiver_address,
                    "receiverPhone": receiver_phone,
                    "status": status,
                    "weight": details.get("packageChargeWeight") or order_info.get("packageChargeWeight"),
                    "lastEventTime": sign_time,
                    "signerName": signer_name
                }
            except Exception:
                return wb, None

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
        report_service = ReportService(client)
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
                    details = data.get("details", {}) or {}
                    order_info = data.get("orderInfo") or data.get("waybillInfo") or {}
                    payload_item["raw"] = {
                        "details": details,
                        "orderInfo": order_info,
                    }
                    payload_item["detail"] = {
                        "waybillNo": waybill_no,
                        "receiverName": (
                            details.get("receiverName")
                            or order_info.get("receiverName")
                            or details.get("receiver")
                        ),
                        "receiverCity": (
                            details.get("receiverCityName")
                            or order_info.get("receiverCityName")
                            or details.get("receiverCity")
                        ),
                        "receiverAddress": (
                            details.get("receiverDetailedAddress")
                            or details.get("receiverAddress")
                            or order_info.get("receiverDetailedAddress")
                        ),
                        "receiverPhone": (
                            details.get("receiverPhone")
                            or order_info.get("receiverPhone")
                            or details.get("consigneePhone")
                        ),
                        "status": (
                            details.get("waybillStatusName")
                            or details.get("statusName")
                            or details.get("status")
                            or order_info.get("waybillStatusName")
                        ),
                        "weight": details.get("packageChargeWeight") or order_info.get("packageChargeWeight"),
                        "signTime": details.get("signTime") or order_info.get("signTime") or "",
                    }
                else:
                    payload_item["errors"].append(
                        detail_response.get("msg") or "No se pudo consultar el detalle oficial."
                    )
            except Exception as exc:
                payload_item["errors"].append(f"detail: {exc}")

            try:
                events = report_service.get_timeline(waybill_no, max_age_minutes=60)
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


@router.get("/{waybill_no}/timeline")
async def get_waybill_timeline(waybill_no: str, max_age_minutes: int = 30):
    normalized_wb = (waybill_no or "").strip().upper()
    if not normalized_wb:
        raise HTTPException(status_code=400, detail="Waybill requerido")

    try:
        def _fetch():
            config = ConfigRepository.get_cached(); client = JTClient(config=config)
            service = ReportService(client)
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
            tracking = client.get_tracking_list(normalized_wb)
            data = tracking.get("data") or []
            scan_time, scan_by_code = _find_signing_event(data)

            if not scan_time or not scan_by_code:
                return {"waybill_no": normalized_wb, "photos": [], "error": "No se encontró evento de firma/entrega"}

            photos_resp = client.get_delivery_photos(normalized_wb, scan_time, scan_by_code)

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
        tracking = client.get_tracking_list(normalized_wb)
        data = tracking.get("data") or []
        scan_time, scan_by_code = _find_signing_event(data)

        if not scan_time or not scan_by_code:
            raise HTTPException(status_code=404, detail="No se encontró evento de firma/entrega")

        photos_resp = client.get_delivery_photos(normalized_wb, scan_time, scan_by_code)

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
