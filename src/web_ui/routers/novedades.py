from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from typing import List, Optional
import os
import shutil
from src.services.novedades_service import NovedadesService
from src.infrastructure.repositories.novedades_repository import NovedadesRepository
from src.infrastructure.database.connection import SessionLocal
from src.domain.exceptions import EntityNotFoundError

router = APIRouter(prefix="/api/novedades", tags=["Novedades"])

@router.post("/")
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
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads", "novedades")
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
        
        with SessionLocal() as db:
            repo = NovedadesRepository(db)
            service = NovedadesService(repo)
            nid = service.create_novedad(waybill, description, status, type_cat, images_paths)
            return {"success": True, "id": nid, "message": "Novedad creada exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def get_novedades(waybill: Optional[str] = None):
    try:
        with SessionLocal() as db:
            repo = NovedadesRepository(db)
            service = NovedadesService(repo)
            if waybill:
                items = service.get_novedades_by_waybill(waybill)
            else:
                items = service.get_all_novedades()
            return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{novedad_id}/status")
async def update_novedad_status(novedad_id: int, payload: dict = Body(...)):
    try:
        new_status = payload.get("status")
        if not new_status:
            raise HTTPException(status_code=400, detail="Missing status")
        with SessionLocal() as db:
            repo = NovedadesRepository(db)
            service = NovedadesService(repo)
            try:
                service.update_novedad_status(novedad_id, new_status)
                return {"success": True}
            except EntityNotFoundError:
                raise HTTPException(status_code=404, detail="Novedad not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
