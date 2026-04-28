from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

import database.models  # noqa: F401
from database.base import Base
from database.service_catalog import seed_services

DB_PATH = Path(__file__).resolve().parent / "bot.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def migrate_db() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "bookings" not in table_names:
        return

    booking_columns = {
        column["name"]
        for column in inspector.get_columns("bookings")
    }
    required_columns = {
        "completed_at": "DATETIME",
        "confirmed_at": "DATETIME",
        "reminder_24h_sent_at": "DATETIME",
        "reminder_3h_sent_at": "DATETIME",
        "admin_unconfirmed_notified_at": "DATETIME",
    }

    with engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name in booking_columns:
                continue
            connection.execute(
                text(
                    f"ALTER TABLE bookings ADD COLUMN {column_name} {column_type}"
                )
            )


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    migrate_db()
    seed_services(SessionLocal())


def get_session() -> Session:
    return SessionLocal()
