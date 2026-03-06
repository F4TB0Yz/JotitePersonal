from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Body, Form, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import concurrent.futures
import shutil
import re
import asyncio
import unicodedata
import time
import base64
import hashlib
import hmac
from datetime import datetime

from src.jt_api.client import JTClient
from src.services.report_service import ReportService
from src.services.temu_alert_service import TemuAlertService
from src.services.temu_prediction_service import temu_prediction_service
from src.services.notification_service import notification_manager
from src.services.novedades_service import novedades_service
from src.services.settlement_service import SettlementService
from src.services.kpi_service import kpi_service
from src.infrastructure.database.connection import SessionLocal, initialize_database
from src.infrastructure.database.models import ConfigORM

app = FastAPI(title="J&T Express Web Reporter")

SESSION_COOKIE_NAME = "jt_session"
SESSION_TTL_SECONDS = 60 * 60 * 12
SESSION_SIGNING_KEY = (
    os.getenv("SESSION_SIGNING_KEY")
    or os.getenv("DASHBOARD_PASSWORD")
    or os.getenv("ADMIN_PASSWORD")
    or os.getenv("APP_PASSWORD")
    or "jt_dashboard_session_key"
)
AUTH_USERNAME = os.getenv("DASHBOARD_USER") or os.getenv("ADMIN_USER") or "admin"


def _is_public_path(path: str) -> bool:
    if path in {"/login", "/api/auth/login", "/api/auth/logout", "/favicon.ico"}:
        return True
    return path.startswith("/static/")


def _resolve_dashboard_password() -> str | None:
    env_password = (
        os.getenv("DASHBOARD_PASSWORD")
        or os.getenv("ADMIN_PASSWORD")
        or os.getenv("APP_PASSWORD")
    )
    if env_password:
        return env_password

    session = None
    try:
        session = SessionLocal()
        token_record = session.query(ConfigORM).filter_by(key="authToken").first()
        if token_record and token_record.value:
            return token_record.value
    except Exception:
        return None
    finally:
        if session:
            session.close()

    return None


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign_payload(payload_b64: str) -> str:
    digest = hmac.new(
        SESSION_SIGNING_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def _create_session_token(username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign_payload(payload_b64)
    return f"{payload_b64}.{signature}"


def _verify_session_token(token: str) -> bool:
    if not token or "." not in token:
        return False

    payload_b64, signature = token.rsplit(".", 1)
    expected_signature = _sign_payload(payload_b64)
    if not hmac.compare_digest(signature, expected_signature):
        return False

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return False

    exp = payload.get("exp")
    sub = payload.get("sub")
    if not isinstance(exp, int) or not isinstance(sub, str) or not sub:
        return False

    return exp >= int(time.time())


def _is_authenticated_request(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    return _verify_session_token(token)


def _is_authenticated_websocket(websocket: WebSocket) -> bool:
    token = websocket.cookies.get(SESSION_COOKIE_NAME, "")
    return _verify_session_token(token)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if _is_public_path(path):
        return await call_next(request)

    if _is_authenticated_request(request):
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    return RedirectResponse(url="/login", status_code=303)


@app.on_event("startup")
async def startup_event():
    temu_prediction_service.start()


@app.on_event("shutdown")
async def shutdown_event():
    await temu_prediction_service.stop()

class TokenUpdate(BaseModel):
    authToken: str


class LoginPayload(BaseModel):
    username: str
    password: str


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


class WaybillReprintPayload(BaseModel):
    waybill_ids: List[str]
    bill_type: str = "small"

@app.post("/api/config/token")
async def update_token(payload: TokenUpdate):
    session = SessionLocal()

    try:
        token_record = session.query(ConfigORM).filter_by(key="authToken").first()

        if token_record:
            if token_record.value == payload.authToken:
                return {"status": "unchanged", "message": "El token ya está actualizado"}
            token_record.value = payload.authToken
        else:
            new_token = ConfigORM(key="authToken", value=payload.authToken)
            session.add(new_token)

        session.commit()
        return {"status": "success", "message": "Token guardado en Postgres como Dios manda"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/login")
async def serve_login(request: Request):
    if _is_authenticated_request(request):
        return RedirectResponse(url="/", status_code=303)
    return FileResponse(os.path.join(templates_dir, "login.html"))


@app.post("/api/auth/login")
async def login(payload: LoginPayload):
    expected_password = _resolve_dashboard_password()
    if not expected_password:
        raise HTTPException(
            status_code=503,
            detail="Login no configurado. Define DASHBOARD_PASSWORD o guarda authToken.",
        )

    valid_user = hmac.compare_digest(payload.username, AUTH_USERNAME)
    valid_password = hmac.compare_digest(payload.password, expected_password)
    if not (valid_user and valid_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    session_token = _create_session_token(payload.username)

    response = JSONResponse(content={"status": "success"})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return response


@app.post("/api/auth/logout")
async def logout(request: Request):
    response = JSONResponse(content={"status": "success"})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(templates_dir, "index.html"))

@app.get("/api/messengers/search")
async def search_messengers(q: str):
    if not q or len(q) < 2:
        return []
    try:
        client = JTClient()
        response = client.search_messengers(q)
        if response.get("code") == 1 and "data" in response:
            return response["data"].get("records", []) if "records" in response["data"] else response["data"]
        return []
    except Exception as e:
        print(f"Error buscando mensajeros: {e}")
        return []


def _normalize_waybill_record(waybill_no: str, details: dict) -> dict:
    return {
        "waybill_no": waybill_no,
        "receiver": details.get("receiverName") or details.get("receiver") or "N/A",
        "city": details.get("receiverCity") or details.get("city") or "N/A",
        "address": details.get("receiverDetailedAddress") or details.get("address") or "N/A",
        "sender": details.get("senderName") or details.get("sender") or "N/A",
        "order_source": details.get("orderSource") or "N/A",
    }


@app.get("/api/search")
async def global_search(q: str, limit: int = 6):
    query = (q or "").strip()
    if len(query) < 2:
        return {"waybills": [], "messengers": [], "novedades": []}

    max_items = max(1, min(limit, 20))
    waybill_results = []
    messenger_results = []
    novedades_results = []

    try:
        client = JTClient()

        maybe_waybill = bool(re.fullmatch(r"[A-Za-z0-9\-]{6,32}", query))
        if maybe_waybill:
            try:
                waybill_no = query.upper()
                detail_resp = client.get_order_detail(waybill_no)
                if detail_resp.get("code") == 1:
                    details = detail_resp.get("data", {}).get("details", {})
                    if details:
                        waybill_results.append(_normalize_waybill_record(waybill_no, details))
            except Exception as wb_error:
                print(f"Error en búsqueda de guía: {wb_error}")

        try:
            messenger_resp = client.search_messengers(query)
            if messenger_resp.get("code") == 1 and "data" in messenger_resp:
                data = messenger_resp.get("data")
                records = data.get("records", []) if isinstance(data, dict) else (data or [])
                messenger_results = records[:max_items]
        except Exception as messenger_error:
            print(f"Error en búsqueda de mensajeros: {messenger_error}")

        try:
            novedades_results = novedades_service.search_novedades(query, limit=max_items)
        except Exception as nov_error:
            print(f"Error en búsqueda de novedades: {nov_error}")

        return {
            "waybills": waybill_results[:max_items],
            "messengers": messenger_results[:max_items],
            "novedades": novedades_results[:max_items],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/messengers/contact")
async def get_messenger_contact(name: str, network_code: str | None = None, waybill: str | None = None):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Nombre requerido")
    try:
        client = JTClient()
        target_network = 1009
        if network_code:
            try:
                target_network = int(network_code)
            except ValueError:
                target_network = 1009
        normalized = name.strip().lower()
        response = client.search_messengers(name.strip(), network_id=target_network)
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
        account_code = best_match.get("accountCode") if best_match else None
        network_name = best_match.get("customerNetworkName") if best_match else None

        if not final_phone and not best_match:
            raise HTTPException(status_code=404, detail="Mensajero no encontrado")

        return {
            "name": final_name,
            "accountCode": account_code,
            "networkName": network_name,
            "phone": final_phone
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/messengers/metrics")
async def get_messenger_metrics(account_code: str, network_code: str, start_time: str, end_time: str):
    if not account_code or not network_code or not start_time or not end_time:
        return {"error": "Missing parameters"}
    try:
        client = JTClient()
        detail = client.get_messenger_metrics(account_code, network_code, start_time, end_time)
        summary = client.get_messenger_metrics_sum(account_code, network_code, start_time, end_time)
        return {
            "detail": detail.get("data", {}).get("records", []) if detail.get("code") == 1 else [],
            "summary": summary.get("data", {}).get("records", []) if summary.get("code") == 1 else []
        }
    except Exception as e:
        print(f"Error obteniendo métricas de mensajero: {e}")
        return {"error": str(e)}

@app.get("/api/messengers/waybills")
async def get_messenger_waybills(account_code: str, network_code: str, start_time: str, end_time: str):
    if not account_code or not network_code or not start_time or not end_time:
        return {"error": "Missing parameters"}
    try:
        client = JTClient()
        return client.get_all_messenger_waybills_detail(account_code, network_code, start_time, end_time)
    except Exception as e:
        print(f"Error obteniendo paquetes de mensajero: {e}")
        return {"error": str(e)}

class WaybillList(BaseModel):
    waybills: List[str]

@app.post("/api/waybills/addresses")
async def get_waybills_addresses(payload: WaybillList):
    """
    Recibe una lista de números de guía y devuelve la dirección de destino.
    Se ejecuta en paralelo para ser más rápido.
    """
    if not payload.waybills:
        return {}

    client = JTClient()
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


@app.post("/api/waybills/phones")
async def get_waybills_phones(payload: WaybillList):
    if not payload.waybills:
        return {}

    client = JTClient()
    try:
        response = client.get_waybill_receiver_phone(payload.waybills)
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


@app.post("/api/waybills/details")
async def get_waybills_details(payload: WaybillList):
    """
    Recibe una lista de guías y devuelve información enriquecida del destinatario
    (nombre, ciudad, dirección, estado, etc.) consultando el detalle oficial.
    """
    if not payload.waybills:
        return {}

    client = JTClient()
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

            # Fallback: extract date and signer from tracking events
            try:
                tracking_resp = client.get_tracking_list(wb)
                tracking_data = tracking_resp.get("data", [])
                if tracking_data:
                    tracking_items = tracking_data[0].get("details", [])
                    # First pass: look for a "firmado" event (preferred)
                    for item in tracking_items:
                        scan_type = (item.get("scanTypeName") or "").lower()
                        if "firmado" in scan_type:
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
                print(f"[waybills/details] {wb}: sign_time={sign_time!r}, signer_name={signer_name!r}")
            except Exception as e:
                print(f"[waybills/details] Tracking fallback error for {wb}: {e}")

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


@app.get("/api/waybills/{waybill_no}/timeline")
async def get_waybill_timeline(waybill_no: str, max_age_minutes: int = 30):
    normalized_wb = (waybill_no or "").strip().upper()
    if not normalized_wb:
        raise HTTPException(status_code=400, detail="Waybill requerido")

    try:
        client = JTClient()
        service = ReportService(client)
        events = service.get_timeline(normalized_wb, max_age_minutes=max_age_minutes)

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

# ---------------------------------------------------------
# WebSocket endpoint para procesamiento en tiempo real
@app.websocket("/ws/process")
async def websocket_process(websocket: WebSocket):
    if not _is_authenticated_websocket(websocket):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    
    try:
        data = await websocket.receive_text()
        request_data = json.loads(data)
        waybills = request_data.get("waybills", [])
        
        if not waybills:
            await websocket.send_json({"type": "error", "message": "No se proporcionaron guías."})
            await websocket.close()
            return

        try:
            client = JTClient()
            service = ReportService(client)
        except Exception as e:
            await websocket.send_json({"type": "error", "message": f"Error inicializando cliente: {e}"})
            await websocket.close()
            return

        for wb in waybills:
            wb = wb.strip()
            if not wb:
                continue
            try:
                # Procesar 1 guía
                data = service.get_consolidated_data(wb)
                result_dict = {
                    "waybill_no": data.waybill_no,
                    "status": data.status,
                    "order_source": data.order_source,
                    "sender": data.sender,
                    "receiver": data.receiver,
                    "city": data.city,
                    "weight": data.weight,
                    "last_event_time": data.last_event_time,
                    "last_network": data.last_network,
                    "last_staff": data.last_staff,
                    "staff_contact": data.staff_contact,
                    "is_delivered": data.is_delivered,
                    "arrival_punto6_time": data.arrival_punto6_time,
                    "delivery_time": data.delivery_time,
                    "address": data.address,
                    "exceptions": data.exceptions,
                    "last_remark": data.last_remark
                }
                # Enviar resultado parcial en tiempo real
                await websocket.send_json({"type": "result", "data": result_dict})
            except Exception as e:
                await websocket.send_json({
                    "type": "result", 
                    "data": {
                        "waybill_no": wb,
                        "status": "Error",
                        "is_delivered": False,
                        "exceptions": str(e)
                    }
                })
        
        # Enviar señal de fin
        await websocket.send_json({"type": "done"})
        
    except WebSocketDisconnect:
        print("Cliente desconectado")
    except Exception as e:
        print(f"Error inesperado: {e}")
        try:
            await websocket.send_json({"type": "error", "message": "Error interno del servidor."})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


@app.post("/api/network/waybills")
async def get_network_waybills(req: dict = Body(...)):
    """
    Endpoint para obtener las guías globales del punto de red.
    Payload esperado:
    {
      "networkCode": "1025006",
      "startTime": "YYYY-MM-DD 00:00:00",
      "endTime": "YYYY-MM-DD 23:59:59",
      "signType": 0 o 1 (0 default para pendientes)
    }
    """
    network_code = req.get("networkCode")
    start_time = req.get("startTime")
    end_time = req.get("endTime")
    sign_type = req.get("signType", 0)

    if not all([network_code, start_time, end_time]):
        raise HTTPException(status_code=400, detail="Faltan parámetros requeridos.")

    def _normalize_text(value: str) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize("NFKD", str(value))
        return "".join(ch for ch in normalized if not unicodedata.combining(ch)).strip().lower()

    def _parse_event_time(value: str) -> datetime | None:
        if not value:
            return None
        cleaned = value.strip()
        known_formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
        )
        for fmt in known_formats:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None

    def _extract_latest_scan_time_by_keywords(events: list, keywords: tuple[str, ...]) -> str:
        latest_value = ""
        latest_dt = None

        for event in events or []:
            type_name = _normalize_text(getattr(event, "type_name", ""))
            if not any(keyword in type_name for keyword in keywords):
                continue

            event_time = (getattr(event, "time", "") or "").strip()
            if not event_time:
                continue

            parsed = _parse_event_time(event_time)
            if parsed is None:
                if not latest_value:
                    latest_value = event_time
                continue

            if latest_dt is None or parsed > latest_dt:
                latest_dt = parsed
                latest_value = event_time

        return latest_value

    try:
        client = JTClient()
        report_service = ReportService(client)
        response = client.get_network_signing_detail(
            network_code=network_code,
            start_time=start_time,
            end_time=end_time,
            sign_type=sign_type
        )

        records = response.get("data", {}).get("records", [])
        if not records:
            return {"records": []}

        unique_waybills = []
        seen_waybills = set()
        for record in records:
            wb = (
                record.get("waybillNo")
                or record.get("billCode")
                or record.get("orderId")
                or ""
            ).strip()
            if not wb or wb in seen_waybills:
                continue
            seen_waybills.add(wb)
            unique_waybills.append(wb)

        scan_data_map = {}

        def fetch_delivery_scan_time(waybill_no: str):
            try:
                events = report_service.get_timeline(waybill_no, max_age_minutes=60)
                latest_delivery_time = _extract_latest_scan_time_by_keywords(
                    events,
                    ("escaneo de entrega",)
                )
                latest_return_time = _extract_latest_scan_time_by_keywords(
                    events,
                    ("escaneo de devolucion", "escaneo devolucion", "devolucion")
                )
                return waybill_no, {
                    "delivery": latest_delivery_time,
                    "return": latest_return_time,
                }
            except Exception:
                return waybill_no, {
                    "delivery": "",
                    "return": "",
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(fetch_delivery_scan_time, wb): wb
                for wb in unique_waybills
            }
            for future in concurrent.futures.as_completed(futures):
                wb, scan_data = future.result()
                scan_data_map[wb] = scan_data

        enriched_records = []
        for record in records:
            wb = (
                record.get("waybillNo")
                or record.get("billCode")
                or record.get("orderId")
                or ""
            ).strip()
            scan_data = scan_data_map.get(wb, {}) if wb else {}
            if scan_data.get("return"):
                continue

            enriched = dict(record)
            enriched["deliveryScanTimeLatest"] = scan_data.get("delivery", "")
            enriched_records.append(enriched)

        return {"records": enriched_records}
    except Exception as e:
        return {"records": [], "error": str(e)}


@app.get("/api/alerts/temu")
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
        client = JTClient()
        service = TemuAlertService(client)
        report = service.build_alert_report(
            threshold_hours=threshold_hours,
            window_hours=window_hours,
            include_overdue=include_overdue,
            duty_agent_code=duty_agent_code,
            duty_code=duty_code,
            manager_code=manager_code,
            responsible_org_code=responsible_org_code,
            dimension_type=dimension_type
        )
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/alerts/temu/predictions")
async def get_temu_predictions(limit: int = 80):
    try:
        return {
            "items": temu_prediction_service.get_recent_predictions(limit=limit),
            "limit": max(1, min(limit, 200)),
            "mode": "predict-72-to-96",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/kpis/overview")
async def get_kpis_overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    ranking_limit: int = 10,
):
    try:
        data = kpi_service.get_overview(
            start_date=start_date,
            end_date=end_date,
            ranking_limit=ranking_limit,
        )
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    if not _is_authenticated_websocket(websocket):
        await websocket.close(code=1008)
        return

    await notification_manager.connect(websocket)
    heartbeat_task = None
    try:
        async def heartbeat():
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "heartbeat", "payload": {"ok": True}})

        heartbeat_task = asyncio.create_task(heartbeat())

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        await notification_manager.disconnect(websocket)

# --- Novedades API Endpoints ---
@app.post("/api/novedades")
async def create_novedad(
    waybill: str = Form(...),
    description: str = Form(...),
    status: str = Form(...),
    type_cat: str = Form(...),
    files: List[UploadFile] = File(None)
):
    try:
        images_paths = []
        if files:
            uploads_dir = os.path.join(os.path.dirname(__file__), "static", "uploads", "novedades")
            os.makedirs(uploads_dir, exist_ok=True)
            for file in files:
                if file.filename:
                    # Clean filename or generate unique one
                    safe_filename = file.filename.replace(" ", "_")
                    file_path = os.path.join(uploads_dir, f"{waybill}_{safe_filename}")
                    with open(file_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    # Store web-accessible path
                    images_paths.append(f"/static/uploads/novedades/{waybill}_{safe_filename}")
        
        nid = novedades_service.create_novedad(waybill, description, status, type_cat, images_paths)
        return {"success": True, "id": nid, "message": "Novedad creada exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/novedades")
async def get_novedades(waybill: Optional[str] = None):
    try:
        if waybill:
            items = novedades_service.get_novedades_by_waybill(waybill)
        else:
            items = novedades_service.get_all_novedades()
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settlements/rate")
async def set_messenger_rate(payload: RatePayload):
    try:
        service = SettlementService(JTClient())
        data = service.set_rate(payload.account_code, payload.account_name, payload.rate_per_delivery)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/settlements/rate")
async def get_messenger_rate(account_code: str):
    try:
        service = SettlementService(JTClient())
        data = service.get_rate(account_code)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/settlements/generate")
async def generate_settlement(payload: SettlementGeneratePayload):
    try:
        service = SettlementService(JTClient())
        data = service.generate_settlement(
            account_code=payload.account_code,
            account_name=payload.account_name,
            network_code=payload.network_code,
            start_time=payload.start_time,
            end_time=payload.end_time,
            deduction_per_issue=payload.deduction_per_issue,
            rate_per_delivery_override=payload.rate_per_delivery,
        )
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/waybills/reprint")
async def reprint_waybills(payload: WaybillReprintPayload):
    try:
        client = JTClient()
        response = client.reprint_waybills(payload.waybill_ids, payload.bill_type)

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


@app.get("/api/settlements")
async def list_settlements(account_code: Optional[str] = None, limit: int = 20):
    try:
        service = SettlementService(JTClient())
        data = service.list_settlements(account_code=account_code, limit=limit)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/settlements/{settlement_id}")
async def get_settlement(settlement_id: int):
    try:
        service = SettlementService(JTClient())
        data = service.get_settlement(settlement_id)
        if not data:
            raise HTTPException(status_code=404, detail="Liquidación no encontrada")
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/api/settlements/{settlement_id}/status")
async def update_settlement_status(settlement_id: int, payload: SettlementStatusPayload):
    try:
        service = SettlementService(JTClient())
        ok = service.update_status(settlement_id, payload.status)
        if not ok:
            raise HTTPException(status_code=404, detail="Liquidación no encontrada")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/settlements/{settlement_id}")
async def delete_settlement(settlement_id: int):
    try:
        service = SettlementService(JTClient())
        ok = service.delete_settlement(settlement_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Liquidación no encontrada")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.put("/api/novedades/{novedad_id}/status")
async def update_novedad_status(novedad_id: int, payload: dict = Body(...)):
    try:
        new_status = payload.get("status")
        if not new_status:
            raise HTTPException(status_code=400, detail="Missing status")
        success = novedades_service.update_novedad_status(novedad_id, new_status)
        if not success:
            raise HTTPException(status_code=404, detail="Novedad not found")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
