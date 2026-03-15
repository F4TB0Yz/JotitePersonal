import json
from sqlalchemy.orm import Session
from sqlalchemy import or_
from src.infrastructure.database.models import NovedadORM

class NovedadesRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, waybill: str, description: str, status: str, type_cat: str, images_json: str) -> int:
        row = NovedadORM(
            waybill=waybill,
            description=description,
            status=status,
            type=type_cat,
            images_json=images_json,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row.id

    def get_all(self) -> list[NovedadORM]:
        return self.session.query(NovedadORM).order_by(NovedadORM.created_at.desc()).all()

    def get_by_waybill(self, waybill: str) -> list[NovedadORM]:
        return (
            self.session.query(NovedadORM)
            .filter(NovedadORM.waybill == waybill)
            .order_by(NovedadORM.created_at.desc())
            .all()
        )

    def get_by_id(self, novedad_id: int) -> NovedadORM | None:
        return self.session.query(NovedadORM).filter(NovedadORM.id == novedad_id).first()

    def update_status(self, novedad_id: int, status: str) -> bool:
        row = self.get_by_id(novedad_id)
        if not row:
            return False
        row.status = status
        self.session.commit()
        return True

    def search(self, pattern: str, limit: int) -> list[NovedadORM]:
        return (
            self.session.query(NovedadORM)
            .filter(
                or_(
                    NovedadORM.waybill.ilike(pattern),
                    NovedadORM.description.ilike(pattern),
                    NovedadORM.type.ilike(pattern),
                    NovedadORM.status.ilike(pattern),
                )
            )
            .order_by(NovedadORM.created_at.desc())
            .limit(limit)
            .all()
        )
