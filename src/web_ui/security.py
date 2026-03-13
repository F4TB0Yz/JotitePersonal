import os
import time
import base64
import hashlib
import hmac
import json
from fastapi import Request, WebSocket
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.database.models import ConfigORM

# Variables de entorno y constantes
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
