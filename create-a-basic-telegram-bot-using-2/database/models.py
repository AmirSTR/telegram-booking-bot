from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(nullable=False)
    time: Mapped[time] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    reminder_24h_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    reminder_3h_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    admin_unconfirmed_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="waiting")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
