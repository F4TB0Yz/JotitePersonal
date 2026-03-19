import hmac
import os
import time
from fastapi import APIRouter, HTTPException, Depends, Request, Body
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import asyncio

from src.infrastructure.database.deps import get_db
from src.infrastructure.database.models import ConfigORM
from src.web_ui import security

router = APIRouter(tags=["Auth"])

class LoginPayload(BaseModel):
    username: str
    password: str

class TokenUpdate(BaseModel):
    authToken: str

@router.get("/login")
async def serve_login(request: Request):
    if security._is_authenticated_request(request):
        return RedirectResponse(url="/", status_code=303)
    templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    return FileResponse(os.path.join(templates_dir, "login.html"))

@router.post("/api/auth/login")
async def login(payload: LoginPayload):
    expected_password = security._resolve_dashboard_password()
    if not expected_password:
        raise HTTPException(
            status_code=503,
            detail="Login no configurado. Define DASHBOARD_PASSWORD o guarda authToken.",
        )

    valid_user = hmac.compare_digest(payload.username, security.AUTH_USERNAME)
    valid_password = hmac.compare_digest(payload.password, expected_password)
    if not (valid_user and valid_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    session_token = security._create_session_token(payload.username)

    response = JSONResponse(content={"status": "success"})
    response.set_cookie(
        key=security.SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=security.SESSION_TTL_SECONDS,
    )
    return response

@router.post("/api/auth/logout")
async def logout(request: Request):
    response = JSONResponse(content={"status": "success"})
    response.delete_cookie(security.SESSION_COOKIE_NAME)
    return response

@router.post("/api/config/token")
async def update_token(payload: TokenUpdate, db: Session = Depends(get_db)):
    try:
        def _update():
            token_record = db.query(ConfigORM).filter_by(key="authToken").first()
            if token_record:
                if token_record.value == payload.authToken:
                    return {"status": "unchanged", "message": "El token ya está actualizado"}
                token_record.value = payload.authToken
            else:
                new_token = ConfigORM(key="authToken", value=payload.authToken)
                db.add(new_token)
            db.commit()
            # Invalidar caché en security
            security._cached_password = None
            security._cached_password_ts = 0
            return {"status": "success", "message": "Token guardado en Postgres como Dios manda"}
        
        return await asyncio.to_thread(_update)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
