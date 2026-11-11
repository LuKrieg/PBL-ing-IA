from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select

from .api import router
from .config import BASE_DIR, CORS_ORIGINS, DEMO_USERS, SEED_DIR, SIM_AUTOSTART
from .db import Base, SessionLocal, engine
from .models import User
from .security import hash_password
from .sim import seed_history, simulator

FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"


class SPAFiles(StaticFiles):
    """Static files with history fallback so deep links like /history work on refresh."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404 and not path.startswith(("api/", "images/")):
                return await super().get_response("index.html", scope)
            raise


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for u in DEMO_USERS:
            if not db.scalar(select(User).where(User.username == u["username"])):
                db.add(User(username=u["username"], name=u["name"], role=u["role"], password_hash=hash_password(u["password"])))
        db.commit()
        seed_history(db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if SIM_AUTOSTART:
        simulator.start()
    yield
    await simulator.stop()


app = FastAPI(title="IMACASA inspection UI backend (PC10 demo)", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

(SEED_DIR / "images").mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=SEED_DIR / "images"), name="images")
if Path(FRONTEND_DIST).exists():  # single-process demo: serve the built SPA too
    app.mount("/", SPAFiles(directory=FRONTEND_DIST, html=True), name="spa")
