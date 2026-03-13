from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import concurrent.futures
from datetime import datetime
from sqlalchemy.orm import Session

from src.infrastructure.database.deps import get_db
from src.infrastructure.database.models import DailyReportEntryORM
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.infrastructure.repositories.tracking_event_repository import TrackingEventRepository
from src.jt_api.client import JTClient
from src.services.report_service import ReportService
from src.infrastructure.database.connection import SessionLocal

router = APIRouter(prefix="/api/daily-report", tags=["Daily Report"])

class DailyReportIngestPayload(BaseModel):
    waybill_nos: List[str]
    report_date: str  # YYYY-MM-DD

@router.post("/entries")
async def ingest_daily_report_entries(payload: DailyReportIngestPayload, db: Session = Depends(get_db)):
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

    def _run_all(session_injected: Session):
        shared_client = JTClient(config=ConfigRepository.get_cached())

        def _process_one(waybill_no: str) -> dict:
            # Concurrencia requiere sesiones separadas por hilo
            session_worker = SessionLocal()
            try:
                tracking_repo = TrackingEventRepository(session_worker)
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
                session_worker.close()

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_process_one, wn): wn for wn in waybill_nos}
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        # Guardado final usando la dependencia inyectada
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
                session_injected.add(entry)
                saved += 1
            session_injected.commit()
        except Exception:
            session_injected.rollback()
            raise

        return {
            "saved": saved,
            "errors": [r for r in results if not r.get("ok")],
        }

    try:
        return await asyncio.to_thread(_run_all, db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/entries")
async def get_daily_report_entries(start_date: str, end_date: str, db: Session = Depends(get_db)):
    """Devuelve las entradas del reporte diario filtradas por rango de fechas."""
    for d in (start_date, end_date):
        try:
            datetime.strptime(d.strip(), "%Y-%m-%d")
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail=f"Fecha inválida: {d}. Usa YYYY-MM-DD")

    def _fetch():
        rows = (
            db.query(DailyReportEntryORM)
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
                "messenger_name": row.last_name if hasattr(row, 'last_name') else row.messenger_name,
                "address": row.address,
                "city": row.city,
                "status": row.status,
                "notes": row.notes or "",
                "report_date": row.report_date,
            }
            if not hasattr(row, 'messenger_name') else
            {
                "id": row.id,
                "waybill_no": row.waybill_no,
                "messenger_name": row.messenger_name,
                "address": row.address,
                "city": row.city,
                "status": row.status,
                "notes": row.notes or "",
                "report_date": row.report_date,
            }
            for row in rows
        ]

    try:
        data = await asyncio.to_thread(_fetch)
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/entries/{entry_id}")
async def delete_daily_report_entry(entry_id: int, db: Session = Depends(get_db)):
    """Elimina una entrada individual del reporte diario."""
    def _delete():
        row = db.query(DailyReportEntryORM).filter_by(id=entry_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Entrada no encontrada")
        db.delete(row)
        db.commit()

    try:
        await asyncio.to_thread(_delete)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

@router.patch("/entries/{entry_id}")
async def update_daily_report_entry(entry_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    """Actualiza notas y/o estado de una entrada del reporte diario."""
    notes = payload.get("notes", "").strip() if isinstance(payload.get("notes"), str) else ""
    status = payload.get("status", "").strip() if isinstance(payload.get("status"), str) else None

    def _update():
        row = db.query(DailyReportEntryORM).filter_by(id=entry_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Entrada no encontrada")
        
        if notes is not None:
            row.notes = notes
        if status is not None:
            row.status = status
        
        db.commit()
        return {
            "id": row.id,
            "waybill_no": row.waybill_no,
            "status": row.status,
            "notes": row.notes or "",
        }

    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
