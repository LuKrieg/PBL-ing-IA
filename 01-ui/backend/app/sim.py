"""Simulated inference: builds inspections from the pre-generated demo image pool."""
import asyncio
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .broker import broker
from .catalog import BY_CODE
from .config import SEED_DIR, SIM_INTERVAL_S
from .db import SessionLocal
from .models import Inspection

DEFECT_WEIGHTS = {
    "PC10": {"poor_finish": 20, "bad_riveting": 18, "rusty_rivets": 12, "handle_misalignment": 16,
             "poor_assembly_fit": 12, "length_out_of_tolerance": 9, "width_out_of_tolerance": 8},
    "PC08": {"dents": 18, "fingerprints": 10, "pores": 12, "spine_waviness": 14, "chipping": 12, "bent_blade": 14,
             "poor_polish": 12, "blistered_blade": 8},
    "PC12": {"handle_misalignment": 18, "dimensions_out_of_spec": 14, "bad_injection": 22, "blocked_skirt": 14,
             "blade_rust": 16, "poor_deburring": 16},
}
DEFECT_RATE = {"PC08": 0.11, "PC10": 0.13, "PC12": 0.09}
MODEL_NAME = "simulated-v0"

_pool: dict[tuple[str, str | None], list[dict]] | None = None


def pool() -> dict:
    global _pool
    if _pool is None:
        _pool = defaultdict(list)
        mf = SEED_DIR / "manifest.json"
        if mf.exists():
            for e in json.loads(mf.read_text()):
                _pool[(e["station"], e["defect"])].append(e)
    return _pool


def _pick_image(rng: random.Random, station: str, defect: str | None) -> dict | None:
    p = pool()
    cands = p.get((station, defect)) or (p.get(("PC10", defect)) if defect == "handle_misalignment" else None)
    if not cands and defect is None:
        cands = p.get(("PC10", None))
    return rng.choice(cands) if cands else None


def make_inspection(rng: random.Random, station: str, ts: datetime, serial_n: int) -> Inspection:
    is_defect = rng.random() < DEFECT_RATE[station]
    defect = None
    if is_defect:
        w = DEFECT_WEIGHTS[station]
        defect = rng.choices(list(w), weights=list(w.values()))[0]
    img = _pick_image(rng, station, defect)
    conf = (min(0.999, max(0.80, rng.betavariate(18, 1.4))) if not defect
            else min(0.995, max(0.55, rng.gauss(0.88, 0.09))))
    return Inspection(
        station=station, ts=ts, serial=f"M980-{serial_n:06d}", verdict="DEFECT" if defect else "OK",
        defect_code=defect, confidence=round(conf, 3),
        bbox=img.get("bbox") if img and defect else None,
        image=img["file"] if img else None, image_w=img.get("w") if img else None, image_h=img.get("h") if img else None,
        source="cv", model=MODEL_NAME, latency_ms=int(max(40, rng.gauss(95, 18))),
        measurement=img["truth"] if img and "length_mm" in (img.get("truth") or {}) else None,
        notes=(img.get("truth") or {}).get("note") if img and defect else None,
    )


def serialize(i: Inspection) -> dict:
    d = BY_CODE.get(i.defect_code) if i.defect_code else None
    return {
        "id": i.id, "station": i.station, "ts": i.ts.astimezone(timezone.utc).isoformat() if i.ts.tzinfo else i.ts.replace(tzinfo=timezone.utc).isoformat(),
        "serial": i.serial, "verdict": i.verdict, "defect_code": i.defect_code,
        "defect_label": d["label"] if d else None, "confidence": i.confidence, "bbox": i.bbox,
        "image_url": f"/images/{i.image}" if i.image else None, "image_w": i.image_w, "image_h": i.image_h,
        "source": i.source, "model": i.model, "latency_ms": i.latency_ms, "measurement": i.measurement, "notes": i.notes,
    }


def next_serial(db: Session) -> int:
    return (db.scalar(select(func.max(Inspection.id))) or 0) + 1000


class Simulator:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.interval = SIM_INTERVAL_S
        self.rng = random.Random()

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def start(self, interval: float | None = None) -> None:
        if interval:
            self.interval = max(0.5, min(60.0, interval))
        if not self.running:
            self.task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval * self.rng.uniform(0.6, 1.4))
            station = self.rng.choices(["PC10", "PC08", "PC12"], weights=[60, 20, 20])[0]
            with SessionLocal() as db:
                row = make_inspection(self.rng, station, datetime.now(timezone.utc), next_serial(db))
                db.add(row)
                db.commit()
                db.refresh(row)
                broker.publish(serialize(row))


simulator = Simulator()


def seed_history(db: Session, days: int = 14) -> None:
    if db.scalar(select(func.count(Inspection.id))):
        return
    rng = random.Random(7)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    n = 1000
    rows = []
    for d in range(days, -1, -1):
        for station, per_day in (("PC10", 90), ("PC08", 55), ("PC12", 55)):
            for _ in range(per_day if d else per_day // 2):
                ts = (now - timedelta(days=d)).replace(hour=rng.randint(6, 17)) + timedelta(
                    minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
                if ts > datetime.now(timezone.utc):
                    continue
                n += 1
                rows.append(make_inspection(rng, station, ts, n))
    rows.sort(key=lambda r: r.ts)
    # manual instrument records for Espesor (cannot be solved with CV)
    for k in range(14):
        ts = now - timedelta(days=rng.randint(0, 13), hours=rng.randint(0, 8))
        bad = k % 5 == 0
        t = round(rng.uniform(3.4, 3.6) if not bad else rng.uniform(2.7, 3.1), 2)
        n += 1
        rows.append(Inspection(station="PC10", ts=ts, serial=f"M980-{n:06d}", verdict="DEFECT" if bad else "OK",
                               defect_code="thickness_out_of_range" if bad else None, confidence=None, source="manual",
                               model="calibrador", measurement={"thickness_mm": t, "nominal_mm": 3.5, "tol_mm": 0.3},
                               notes="Medido con calibrador (instrumento)"))
    db.add_all(rows)
    db.commit()
