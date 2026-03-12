"""
Migration helpers to ensure table schema is up-to-date.
Handles adding new columns to existing tables without disrupting existing data.
"""

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
import logging

from .models import ReturnApplicationSnapshotORM

logger = logging.getLogger(__name__)


def ensure_daily_report_notes_column(engine) -> bool:
    """
    Ensures that the daily_report_entries table has the 'notes' column.
    Returns True if successful, False otherwise.
    """
    try:
        # Check if the column already exists
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("daily_report_entries")]
        
        if "notes" in columns:
            logger.info("Column 'notes' already exists in daily_report_entries table.")
            return True
        
        # Add the column if it doesn't exist
        with engine.connect() as conn:
            # For PostgreSQL and most databases
            conn.execute(text("ALTER TABLE daily_report_entries ADD COLUMN notes TEXT DEFAULT ''"))
            conn.commit()
            logger.info("Successfully added 'notes' column to daily_report_entries table.")
        return True
    except SQLAlchemyError as e:
        logger.warning(f"Could not add 'notes' column (may already exist or DB unavailable): {e}")
        # Don't fail hard - maybe the column already exists or DB is in read-only mode
        return False
    except Exception as e:
        logger.warning(f"Unexpected error during migration: {e}")
        return False


def ensure_daily_report_updated_at_column(engine) -> bool:
    """
    Ensures that the daily_report_entries table has the 'updated_at' column.
    Returns True if successful, False otherwise.
    """
    try:
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("daily_report_entries")]
        
        if "updated_at" in columns:
            logger.info("Column 'updated_at' already exists in daily_report_entries table.")
            return True
        
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE daily_report_entries ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ))
            conn.commit()
            logger.info("Successfully added 'updated_at' column to daily_report_entries table.")
        return True
    except SQLAlchemyError as e:
        logger.warning(f"Could not add 'updated_at' column (may already exist or DB unavailable): {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error during migration: {e}")
        return False


def run_all_migrations(engine) -> None:
    """
    Runs all pending migrations.
    """
    ensure_daily_report_notes_column(engine)
    ensure_daily_report_updated_at_column(engine)
    ensure_return_snapshots_table(engine)


def ensure_return_snapshots_table(engine) -> bool:
    """Ensures return_application_snapshots table and indexes exist."""
    try:
        table = ReturnApplicationSnapshotORM.__table__
        table.create(bind=engine, checkfirst=True)
        for index in table.indexes:
            index.create(bind=engine, checkfirst=True)
        logger.info("Ensured return_application_snapshots table and indexes.")
        return True
    except SQLAlchemyError as e:
        logger.warning(f"Could not ensure return_application_snapshots table: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error ensuring return_application_snapshots table: {e}")
        return False
