from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Body, Form, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import io
import json
import zipfile
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
from urllib.parse import urlparse


from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository

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


_cached_password: str | None = None
_cached_password_ts: float = 0
_CACHE_TTL = 60  # segundos


def _resolve_dashboard_password() -> str | None:
    global _cached_password, _cached_password_ts

    now = time.monotonic()
    if _cached_password is not None and (now - _cached_password_ts) < _CACHE_TTL:
        return _cached_password

    env_password = (
        os.getenv("DASHBOARD_PASSWORD")
        or os.getenv("ADMIN_PASSWORD")
        or os.getenv("APP_PASSWORD")
    )
    if env_password:
        _cached_password = env_password
        _cached_password_ts = now
        return env_password

    session = None
    try:
        session = SessionLocal()
        token_record = session.query(ConfigORM).filter_by(key="authToken").first()
        if token_record and token_record.value:
            _cached_password = token_record.value
            _cached_password_ts = now
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
    global _cached_password, _cached_password_ts

    def _update():
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

    result = await asyncio.to_thread(_update)
    # Invalidar caché de password para que surta efecto de inmediato
    _cached_password = None
    _cached_password_ts = 0
    return result

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
        def _search():
            config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
            return client.search_messengers(q)

        response = await asyncio.to_thread(_search)
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

    def _search():
        waybill_results = []
        messenger_results = []
        novedades_results = []

        config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)

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

    try:
        return await asyncio.to_thread(_search)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/messengers/contact")
async def get_messenger_contact(name: str, network_code: str | None = None, waybill: str | None = None):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Nombre requerido")

    def _fetch_contact():
        config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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

    try:
        return await asyncio.to_thread(_fetch_contact)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/messengers/metrics")
async def get_messenger_metrics(account_code: str, network_code: str, start_time: str, end_time: str):
    if not account_code or not network_code or not start_time or not end_time:
        return {"error": "Missing parameters"}
    try:
        def _fetch():
            config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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

@app.get("/api/messengers/waybills")
async def get_messenger_waybills(account_code: str, network_code: str, start_time: str, end_time: str):
    if not account_code or not network_code or not start_time or not end_time:
        return {"error": "Missing parameters"}
    try:
        def _fetch():
            config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
            return client.get_all_messenger_waybills_detail(account_code, network_code, start_time, end_time)
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        print(f"Error obteniendo paquetes de mensajero: {e}")
        return {"error": str(e)}

class MessengerItem(BaseModel):
    accountCode: str
    networkCode: str
    accountName: str

class BulkMetricsRequest(BaseModel):
    messengers: List[MessengerItem]
    startTime: str
    endTime: str

@app.post("/api/messengers/bulk-metrics")
async def get_bulk_messenger_metrics(payload: BulkMetricsRequest):
    if not payload.messengers or not payload.startTime or not payload.endTime:
        return {"error": "Missing parameters"}
    if len(payload.messengers) > 30:
        raise HTTPException(status_code=400, detail="Máximo 30 mensajeros por consulta")

    async def _fetch_one(m: MessengerItem):
        try:
            def _call():
                config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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

@app.get("/api/messengers/daily-report")
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
        config = ConfigRepository(SessionLocal()).load_config()
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

    def _fetch_all():
        config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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


@app.post("/api/waybills/phones")
async def get_waybills_phones(payload: WaybillList):
    if not payload.waybills:
        return {}

    def _fetch():
        config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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


@app.post("/api/waybills/details")
async def get_waybills_details(payload: WaybillList):
    """
    Recibe una lista de guías y devuelve información enriquecida del destinatario
    (nombre, ciudad, dirección, estado, etc.) consultando el detalle oficial.
    """
    if not payload.waybills:
        return {}

    def _fetch_all():
        config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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

    return await asyncio.to_thread(_fetch_all)


@app.post("/api/waybills/intelligence-export")
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
        config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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


@app.get("/api/waybills/{waybill_no}/timeline")
async def get_waybill_timeline(waybill_no: str, max_age_minutes: int = 30):
    normalized_wb = (waybill_no or "").strip().upper()
    if not normalized_wb:
        raise HTTPException(status_code=400, detail="Waybill requerido")

    try:
        def _fetch():
            config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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
            config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
            service = ReportService(client, TrackingEventRepository(SessionLocal()))
        except Exception as e:
            await websocket.send_json({"type": "error", "message": f"Error inicializando cliente: {e}"})
            await websocket.close()
            return

        for wb in waybills:
            wb = wb.strip()
            if not wb:
                continue
            try:
                # Procesar 1 guía (en hilo separado para no bloquear el event loop)
                data = await asyncio.to_thread(service.get_consolidated_data, wb)
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

    try:
        def _fetch_network():
            config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
            response = client.get_network_signing_detail(
                network_code=network_code,
                start_time=start_time,
                end_time=end_time,
                sign_type=sign_type
            )
            records = response.get("data", {}).get("records", [])
            return {"records": records or []}

        return await asyncio.to_thread(_fetch_network)
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
        def _fetch():
            config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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
                await asyncio.sleep(20)
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
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository(SessionLocal()).load_config()))
            return service.set_rate(payload.account_code, payload.account_name, payload.rate_per_delivery)
        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/settlements/rate")
async def get_messenger_rate(account_code: str):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository(SessionLocal()).load_config()))
            return service.get_rate(account_code)
        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/settlements/generate")
async def generate_settlement(payload: SettlementGeneratePayload):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository(SessionLocal()).load_config()))
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


@app.post("/api/waybills/reprint")
async def reprint_waybills(payload: WaybillReprintPayload):
    try:
        def _fetch():
            config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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


@app.get("/api/settlements")
async def list_settlements(account_code: Optional[str] = None, limit: int = 20):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository(SessionLocal()).load_config()))
            return service.list_settlements(account_code=account_code, limit=limit)
        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/settlements/{settlement_id}")
async def get_settlement(settlement_id: int):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository(SessionLocal()).load_config()))
            return service.get_settlement(settlement_id)
        data = await asyncio.to_thread(_run)
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
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository(SessionLocal()).load_config()))
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


@app.delete("/api/settlements/{settlement_id}")
async def delete_settlement(settlement_id: int):
    try:
        def _run():
            service = SettlementService(JTClient(config=ConfigRepository(SessionLocal()).load_config()))
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

# ---------------------------------------------------------
# Fotos de entrega

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


@app.get("/api/waybills/{waybill_no}/photos")
async def get_waybill_photos(waybill_no: str):
    normalized_wb = (waybill_no or "").strip().upper()
    if not normalized_wb:
        raise HTTPException(status_code=400, detail="Waybill requerido")

    try:
        def _fetch():
            config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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


@app.get("/api/waybills/{waybill_no}/photos/download")
async def download_waybill_photos(waybill_no: str):
    import requests as _requests

    normalized_wb = (waybill_no or "").strip().upper()
    if not normalized_wb:
        raise HTTPException(status_code=400, detail="Waybill requerido")

    def _fetch():
        config = ConfigRepository(SessionLocal()).load_config(); client = JTClient(config=config)
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


@app.get("/api/photos/proxy")
async def proxy_photo(url: str, filename: str = "foto.jpeg"):
    """Descarga una foto externa y la sirve como attachment (evita restricción cross-origin del browser)."""
    import requests as _requests

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


# ---------------------------------------------------------
# Reporte diario de guías

from src.infrastructure.database.models import DailyReportEntryORM  # noqa: E402


class DailyReportIngestPayload(BaseModel):
    waybill_nos: List[str]
    report_date: str  # YYYY-MM-DD


@app.post("/api/daily-report/entries")
async def ingest_daily_report_entries(payload: DailyReportIngestPayload):
    """Consulta J&T por cada guía y guarda los datos en BD local."""
    raw_date = (payload.report_date or "").strip()
    if not raw_date:
        raise HTTPException(status_code=400, detail="report_date requerido (YYYY-MM-DD)")
    try:
        datetime.strptime(raw_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="report_date inválido. Usa YYYY-MM-DD")

    waybill_nos = [w.strip().upper() for w in payload.waybill_nos if w.strip()]
    if not waybill_nos:
        raise HTTPException(status_code=400, detail="Debes enviar al menos una guía")
    if len(waybill_nos) > 200:
        raise HTTPException(status_code=400, detail="Máximo 200 guías por solicitud")

    def _run_all():
        # Load config and build client ONCE for all worker threads
        cfg_session = SessionLocal()
        try:
            config = ConfigRepository(cfg_session).load_config()
        finally:
            cfg_session.close()
        shared_client = JTClient(config=config)

        def _process_one(waybill_no: str) -> dict:
            session = SessionLocal()
            try:
                tracking_repo = TrackingEventRepository(session)
                service = ReportService(shared_client, tracking_repo=tracking_repo)
                try:
                    row = service.get_consolidated_data(waybill_no)
                    return {
                        "waybill_no": row.waybill_no,
                        "messenger_name": row.last_staff or "",
                        "address": row.address or "",
                        "city": row.city or "",
                        "status": row.status or "",
                        "ok": True,
                    }
                except Exception as exc:
                    return {"waybill_no": waybill_no, "ok": False, "error": str(exc)}
            finally:
                session.close()

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_process_one, wn): wn for wn in waybill_nos}
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        session = SessionLocal()
        try:
            saved = 0
            for r in results:
                if not r.get("ok"):
                    continue
                entry = DailyReportEntryORM(
                    waybill_no=r["waybill_no"],
                    messenger_name=r["messenger_name"],
                    address=r["address"],
                    city=r["city"],
                    status=r["status"],
                    report_date=raw_date,
                )
                session.add(entry)
                saved += 1
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return {
            "saved": saved,
            "errors": [r for r in results if not r.get("ok")],
        }

    try:
        return await asyncio.to_thread(_run_all)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/daily-report/entries")
async def get_daily_report_entries(start_date: str, end_date: str):
    """Devuelve las entradas del reporte diario filtradas por rango de fechas."""
    for d in (start_date, end_date):
        try:
            datetime.strptime(d.strip(), "%Y-%m-%d")
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail=f"Fecha inválida: {d}. Usa YYYY-MM-DD")

    def _fetch():
        session = SessionLocal()
        try:
            rows = (
                session.query(DailyReportEntryORM)
                .filter(
                    DailyReportEntryORM.report_date >= start_date.strip(),
                    DailyReportEntryORM.report_date <= end_date.strip(),
                )
                .order_by(DailyReportEntryORM.report_date.desc(), DailyReportEntryORM.id.asc())
                .all()
            )
            return [
                {
                    "id": row.id,
                    "waybill_no": row.waybill_no,
                    "messenger_name": row.messenger_name,
                    "address": row.address,
                    "city": row.city,
                    "status": row.status,
                    "report_date": row.report_date,
                }
                for row in rows
            ]
        finally:
            session.close()

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/daily-report/entries/{entry_id}")
async def delete_daily_report_entry(entry_id: int):
    """Elimina una entrada individual del reporte diario."""
    def _delete():
        session = SessionLocal()
        try:
            row = session.query(DailyReportEntryORM).filter_by(id=entry_id).first()
            if not row:
                raise HTTPException(status_code=404, detail="Entrada no encontrada")
            session.delete(row)
            session.commit()
        except HTTPException:
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    try:
        await asyncio.to_thread(_delete)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
