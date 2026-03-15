from datetime import datetime
from sqlalchemy.orm import Session
from src.infrastructure.database.models import SettlementORM, NovedadORM

class KPIRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_settlements(self, start: datetime | None, end: datetime | None) -> list[SettlementORM]:
        query = self.session.query(SettlementORM)
        if start:
            query = query.filter(SettlementORM.generated_at >= start)
        if end:
            query = query.filter(SettlementORM.generated_at <= end)
        return query.order_by(SettlementORM.generated_at.desc()).all()

    def get_novedades(self, start: datetime | None, end: datetime | None) -> list[NovedadORM]:
        query = self.session.query(NovedadORM)
        if start:
            query = query.filter(NovedadORM.created_at >= start)
        if end:
            query = query.filter(NovedadORM.created_at <= end)
        return query.order_by(NovedadORM.created_at.desc()).all()
