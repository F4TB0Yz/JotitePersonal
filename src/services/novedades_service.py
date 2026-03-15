import json
from typing import List, Dict, Any

from src.infrastructure.repositories.novedades_repository import NovedadesRepository
from src.domain.exceptions import EntityNotFoundError


class NovedadesService:
    def __init__(self, repository: NovedadesRepository):
        self.repository = repository

    def create_novedad(self, waybill: str, description: str, status: str, type_cat: str, images: List[str]) -> int:
        images_json = json.dumps(images or [])
        return self.repository.create(
            waybill=waybill,
            description=description,
            status=status,
            type_cat=type_cat,
            images_json=images_json
        )

    @staticmethod
    def _to_dict(row) -> Dict[str, Any]:
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
        rows = self.repository.get_all()
        return [self._to_dict(row) for row in rows]

    def get_novedades_by_waybill(self, waybill: str) -> List[Dict[str, Any]]:
        rows = self.repository.get_by_waybill(waybill)
        return [self._to_dict(row) for row in rows]

    def update_novedad_status(self, novedad_id: int, status: str) -> bool:
        ok = self.repository.update_status(novedad_id, status)
        if not ok:
            raise EntityNotFoundError(f"Novedad with id {novedad_id} not found")
        return True

    def search_novedades(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        term = (query or "").strip()
        if len(term) < 2:
            return []
        pattern = f"%{term}%"
        rows = self.repository.search(pattern, max(1, min(limit, 50)))
        return [self._to_dict(row) for row in rows]
