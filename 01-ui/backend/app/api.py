import asyncio
import json
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from .broker import broker
from .catalog import BY_CODE, CATALOG, STATIONS, defects_for
from .db import get_db
from .models import Inspection, User
from .security import current_user, make_token, require_admin, user_from_query_token, verify_password
from .sim import MODEL_NAME, next_serial, serialize, simulator

router = APIRouter(prefix="/api")
STATION_CODES = {s["code"] for s in STATIONS}


class LoginIn(BaseModel):
    username: str
    password: str


def _user_out(u: User) -> dict:
    return {"id": u.id, "username": u.username, "name": u.name, "role": u.role}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    # Same error for unknown user and wrong password.
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    return {"access_token": make_token(user), "token_type": "bearer", "user": _user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return _user_out(user)


@router.get("/catalog")
def catalog(_: User = Depends(current_user)):
    return {"stations": STATIONS, "defects": CATALOG}


def _parse_date(s: str | None, end: bool = False) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        raise HTTPException(422, f"Fecha inválida: {s}")
    if len(s) <= 10:  # date only -> whole day
        d = datetime.combine(d.date(), time.max if end else time.min)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


@router.get("/stations")
def stations(db: Session = Depends(get_db), _: User = Depends(current_user)):
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    out = []
    for s in STATIONS:
        q = select(func.count(Inspection.id), func.sum(case((Inspection.verdict == "DEFECT", 1), else_=0))).where(
            and_(Inspection.station == s["code"], Inspection.ts >= since))
        total, defects = db.execute(q).one()
        last = db.scalar(select(Inspection).where(Inspection.station == s["code"]).order_by(Inspection.ts.desc()).limit(1))
        total, defects = total or 0, int(defects or 0)
        out.append({**s, "defects": defects_for(s["code"]), "total_24h": total, "defects_24h": defects,
                    "defect_rate_24h": round(defects / total, 4) if total else 0.0,
                    "last": serialize(last) if last else None})
    return out


@router.get("/inspections")
def list_inspections(
    station: str | None = None, defect: str | None = None, verdict: str | None = None,
    date_from: str | None = None, date_to: str | None = None, q: str | None = None, source: str | None = None,
    sort: str = "desc", page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db), _: User = Depends(current_user),
):
    conds = []
    if station:
        if station not in STATION_CODES:
            raise HTTPException(422, "Estación inválida")
        conds.append(Inspection.station == station)
    if defect:
        conds.append(Inspection.defect_code == defect)
    if verdict:
        conds.append(Inspection.verdict == verdict.upper())
    if source:
        conds.append(Inspection.source == source)
    if df := _parse_date(date_from):
        conds.append(Inspection.ts >= df)
    if dt := _parse_date(date_to, end=True):
        conds.append(Inspection.ts <= dt)
    if q:
        conds.append(Inspection.serial.ilike(f"%{q.strip()}%"))
    where = and_(*conds) if conds else True
    total = db.scalar(select(func.count(Inspection.id)).where(where)) or 0
    order = Inspection.ts.asc() if sort == "asc" else Inspection.ts.desc()
    rows = db.scalars(select(Inspection).where(where).order_by(order, Inspection.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/inspections/{iid}")
def get_inspection(iid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    row = db.get(Inspection, iid)
    if not row:
        raise HTTPException(404, "Inspección no encontrada")
    return serialize(row)


class ManualIn(BaseModel):
    station: str
    serial: str | None = Field(None, max_length=24)
    thickness_mm: float | None = Field(None, gt=0, lt=50)
    nominal_mm: float = 3.5
    tol_mm: float = 0.3
    defect_code: str | None = None
    notes: str | None = Field(None, max_length=400)


@router.post("/inspections/manual", status_code=201)
def manual_entry(body: ManualIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Registers a point that stays with instruments (e.g. Espesor with a caliper)."""
    if body.station not in STATION_CODES:
        raise HTTPException(422, "Estación inválida")
    code = body.defect_code
    meas = None
    if body.thickness_mm is not None:
        meas = {"thickness_mm": body.thickness_mm, "nominal_mm": body.nominal_mm, "tol_mm": body.tol_mm}
        out = abs(body.thickness_mm - body.nominal_mm) > body.tol_mm
        code = "thickness_out_of_range" if out else None
    if code and (code not in BY_CODE or body.station not in BY_CODE[code]["stations"]):
        raise HTTPException(422, "Defecto no válido para la estación")
    row = Inspection(station=body.station, ts=datetime.now(timezone.utc), serial=body.serial or f"M980-{next_serial(db):06d}",
                     verdict="DEFECT" if code else "OK", defect_code=code, source="manual", model="instrumento",
                     measurement=meas, notes=body.notes, operator_id=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    out = serialize(row)
    broker.publish(out)
    return out


@router.get("/stats")
def stats(station: str | None = None, days: int = Query(7, ge=1, le=60), db: Session = Depends(get_db),
          _: User = Depends(current_user)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    conds = [Inspection.ts >= since] + ([Inspection.station == station] if station else [])
    where = and_(*conds)
    by_defect = db.execute(select(Inspection.defect_code, func.count()).where(and_(where, Inspection.verdict == "DEFECT"))
                           .group_by(Inspection.defect_code).order_by(func.count().desc())).all()
    day = func.strftime("%Y-%m-%d", Inspection.ts)
    series = db.execute(select(day, Inspection.station, func.count(), func.sum(case((Inspection.verdict == "DEFECT", 1), else_=0)))
                        .where(where).group_by(day, Inspection.station).order_by(day)).all()
    total = db.scalar(select(func.count()).where(where)) or 0
    defects = db.scalar(select(func.count()).where(and_(where, Inspection.verdict == "DEFECT"))) or 0
    return {
        "total": total, "defects": defects, "defect_rate": round(defects / total, 4) if total else 0.0,
        "by_defect": [{"code": c, "label": BY_CODE.get(c, {}).get("label", c), "count": n} for c, n in by_defect],
        "series": [{"day": d, "station": s, "total": t, "defects": int(x or 0)} for d, s, t, x in series],
    }


@router.get("/stream")
async def stream(request: Request, station: str | None = None, user: User = Depends(user_from_query_token)):
    q = broker.subscribe()

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if station and ev["station"] != station:
                    continue
                yield f"event: inspection\ndata: {json.dumps(ev)}\n\n"
        finally:
            broker.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/simulator")
def sim_status(_: User = Depends(current_user)):
    return {"running": simulator.running, "interval_s": simulator.interval, "model": MODEL_NAME}


@router.post("/simulator/start")
def sim_start(interval_s: float | None = None, _: User = Depends(require_admin)):
    simulator.start(interval_s)
    return {"running": simulator.running, "interval_s": simulator.interval}


@router.post("/simulator/stop")
async def sim_stop(_: User = Depends(require_admin)):
    await simulator.stop()
    return {"running": simulator.running, "interval_s": simulator.interval}
