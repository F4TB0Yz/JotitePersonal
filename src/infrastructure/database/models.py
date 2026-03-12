from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class NovedadORM(Base):
    __tablename__ = "novedades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    waybill = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    type = Column(String, nullable=False)
    images_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class TrackingEventORM(Base):
    __tablename__ = "tracking_events"
    __table_args__ = (
        UniqueConstraint("waybill_no", "time", "type_name", name="uq_tracking_event_identity"),
        Index("ix_tracking_waybill_time", "waybill_no", "time"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    waybill_no = Column(String, nullable=False, index=True)
    time = Column(String, nullable=False)
    type_name = Column(String, nullable=False)
    network_name = Column(String, nullable=True)
    staff_name = Column(String, nullable=True)
    staff_contact = Column(String, nullable=True)
    status = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    fetched_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False, index=True)


class TemuPredictionORM(Base):
    __tablename__ = "temu_predictions"
    __table_args__ = (
        Index("ix_temu_prediction_status", "status"),
        Index("ix_temu_prediction_predicted", "predicted_96_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    billcode = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="active")
    first_seen_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    last_seen_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    predicted_96_at = Column(DateTime, nullable=False)
    last_hours_since = Column(String, nullable=True)
    notified_at = Column(DateTime, nullable=True)
    payload_json = Column(Text, nullable=True)


class MessengerRateORM(Base):
    __tablename__ = "messenger_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_code = Column(String, nullable=False, unique=True, index=True)
    account_name = Column(String, nullable=False)
    rate_per_delivery = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class SettlementORM(Base):
    __tablename__ = "settlements"
    __table_args__ = (
        Index("ix_settlement_account_generated", "account_code", "generated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_code = Column(String, nullable=False, index=True)
    account_name = Column(String, nullable=False)
    network_code = Column(String, nullable=True)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    total_waybills = Column(Integer, nullable=False, default=0)
    total_delivered = Column(Integer, nullable=False, default=0)
    total_pending = Column(Integer, nullable=False, default=0)
    deduction_count = Column(Integer, nullable=False, default=0)
    deduction_total = Column(String, nullable=False, default="0")
    rate_per_delivery = Column(String, nullable=False, default="0")
    total_amount = Column(String, nullable=False, default="0")
    status = Column(String, nullable=False, default="borrador")
    detail_json = Column(Text, nullable=True)
    generated_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)


class ConfigORM(Base):
    __tablename__ = "configuracion"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)


class DailyReportEntryORM(Base):
    __tablename__ = "daily_report_entries"
    __table_args__ = (
        Index("ix_daily_report_date", "report_date"),
        Index("ix_daily_report_waybill", "waybill_no"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    waybill_no = Column(String, nullable=False)
    messenger_name = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String, nullable=True)
    status = Column(String, nullable=True)
    notes = Column(Text, nullable=True, default='')  # Notas/comentarios del operador
    report_date = Column(String, nullable=False)  # YYYY-MM-DD
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
