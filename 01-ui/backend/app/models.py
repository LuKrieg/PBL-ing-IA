from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))


class Inspection(Base):
    __tablename__ = "inspections"
    id: Mapped[int] = mapped_column(primary_key=True)
    station: Mapped[str] = mapped_column(String(8), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=utcnow)
    serial: Mapped[str] = mapped_column(String(24))
    verdict: Mapped[str] = mapped_column(String(8), index=True)  # OK | DEFECT
    defect_code: Mapped[str | None] = mapped_column(String(48), index=True, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [x0, y0, x1, y1] in image px
    image: Mapped[str | None] = mapped_column(String(200), nullable=True)
    image_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(12), default="cv")  # cv | manual
    model: Mapped[str] = mapped_column(String(60), default="simulated")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    measurement: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(400), nullable=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


Index("ix_insp_station_ts", Inspection.station, Inspection.ts)
