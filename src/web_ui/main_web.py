import os
import logging
import asyncio
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from src.web_ui.routers import (
    waybills, 
    messengers, 
    returns, 
    settlements, 
    novedades, 
    daily_report, 
    auth, 
    ws, 
    dashboard,
    config
)
from src.infrastructure.database.connection import initialize_database, SessionLocal
from src.web_ui import security
from src.services.temu_prediction_service import temu_prediction_service

# Inicialización de la aplicación
app = FastAPI(title="J&T Express Web Reporter")

# Inclusión de Routers
app.include_router(waybills.router)
app.include_router(messengers.router)
app.include_router(returns.router)
app.include_router(settlements.router)
app.include_router(novedades.router)
app.include_router(daily_report.router)
app.include_router(auth.router)
app.include_router(ws.router)
app.include_router(dashboard.router)
app.include_router(config.router)

logger = logging.getLogger(__name__)

# Middleware de Autenticación
def _is_public_path(path: str) -> bool:
    if path in {"/login", "/api/auth/login", "/api/auth/logout", "/favicon.ico"}:
        return True
    return path.startswith("/static/")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if _is_public_path(path):
        return await call_next(request)

    if security._is_authenticated_request(request):
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    return RedirectResponse(url="/login", status_code=303)

# Ciclo de vida (Startup/Shutdown)
_returns_sync_task: asyncio.Task | None = None

def _run_returns_sync_cycle() -> dict:
    # Función auxiliar para el loop de sincronización de devoluciones
    lookback_days = int(os.getenv("RETURNS_SYNC_LOOKBACK_DAYS", "2"))
    sync_size = int(os.getenv("RETURNS_SYNC_PAGE_SIZE", "50"))
    sync_max_pages = int(os.getenv("RETURNS_SYNC_MAX_PAGES", "20"))
    start_time, end_time = returns._resolve_returns_range(None, None, lookback_days=lookback_days)
    with SessionLocal() as db_session:
        service = returns._build_returns_service(db_session)
        return service.sync_statuses(
            apply_time_from=start_time,
            apply_time_to=end_time,
            statuses=(1, 2, 3),
            size=sync_size,
            max_pages=sync_max_pages,
        )

async def _returns_sync_loop() -> None:
    interval = max(60, int(os.getenv("RETURNS_SYNC_INTERVAL_SECONDS", "900")))
    while True:
        try:
            async with returns.returns_sync_lock:
                summary = await asyncio.to_thread(_run_returns_sync_cycle)
                logger.info("Returns sync cycle done: %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Returns sync cycle failed: %s", exc)
        await asyncio.sleep(interval)

@app.on_event("startup")
async def startup_event():
    global _returns_sync_task
    # Inicialización de DB en SEGUNDO PLANO para no bloquear el arranque de Heroku (Boot Timeout)
    asyncio.create_task(asyncio.to_thread(initialize_database))
    temu_prediction_service.start()
    _returns_sync_task = asyncio.create_task(_returns_sync_loop())

@app.on_event("shutdown")
async def shutdown_event():
    global _returns_sync_task
    if _returns_sync_task:
        _returns_sync_task.cancel()
        try:
            await _returns_sync_task
        except asyncio.CancelledError:
            pass
        _returns_sync_task = None
    await temu_prediction_service.stop()

# Configuración de Archivos Estáticos y Templates
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon():
    return FileResponse(os.path.join(static_dir, "favicon.webp"), media_type="image/webp")

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(templates_dir, "index.html"))
