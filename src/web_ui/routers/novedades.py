from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from typing import List, Optional
import os
import shutil
from src.services.novedades_service import novedades_service

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
        
        nid = novedades_service.create_novedad(waybill, description, status, type_cat, images_paths)
        return {"success": True, "id": nid, "message": "Novedad creada exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def get_novedades(waybill: Optional[str] = None):
    try:
        if waybill:
            items = novedades_service.get_novedades_by_waybill(waybill)
        else:
            items = novedades_service.get_all_novedades()
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{novedad_id}/status")
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
