import json
import os
from typing import List, Dict, Any

from sqlalchemy import or_

from src.infrastructure.database.connection import SessionLocal, initialize_database
from src.infrastructure.database.models import NovedadORM

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")

class NovedadesService:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        initialize_database()

    def create_novedad(self, waybill: str, description: str, status: str, type_cat: str, images: List[str]) -> int:
        images_json = json.dumps(images or [])
        with SessionLocal() as session:
            row = NovedadORM(
                waybill=waybill,
                description=description,
                status=status,
                type=type_cat,
                images_json=images_json,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id

    @staticmethod
    def _to_dict(row: NovedadORM) -> Dict[str, Any]:
        return {
            "id": row.id,
            "waybill": row.waybill,
            "description": row.description,
            "status": row.status,
            "type": row.type,
            "images": json.loads(row.images_json or "[]"),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def get_all_novedades(self) -> List[Dict[str, Any]]:
        with SessionLocal() as session:
            rows = session.query(NovedadORM).order_by(NovedadORM.created_at.desc()).all()
            return [self._to_dict(row) for row in rows]
            
    def get_novedades_by_waybill(self, waybill: str) -> List[Dict[str, Any]]:
        with SessionLocal() as session:
            rows = (
                session.query(NovedadORM)
                .filter(NovedadORM.waybill == waybill)
                .order_by(NovedadORM.created_at.desc())
                .all()
            )
            return [self._to_dict(row) for row in rows]

    def update_novedad_status(self, novedad_id: int, status: str) -> bool:
        with SessionLocal() as session:
            row = session.query(NovedadORM).filter(NovedadORM.id == novedad_id).first()
            if not row:
                return False
            row.status = status
            session.commit()
            return True

    def search_novedades(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        term = (query or "").strip()
        if len(term) < 2:
            return []
        pattern = f"%{term}%"
        with SessionLocal() as session:
            rows = (
                session.query(NovedadORM)
                .filter(
                    or_(
                        NovedadORM.waybill.ilike(pattern),
                        NovedadORM.description.ilike(pattern),
                        NovedadORM.type.ilike(pattern),
                        NovedadORM.status.ilike(pattern),
                    )
                )
                .order_by(NovedadORM.created_at.desc())
                .limit(max(1, min(limit, 50)))
                .all()
            )
            return [self._to_dict(row) for row in rows]

novedades_service = NovedadesService()
