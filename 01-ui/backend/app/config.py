import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SEED_DIR = BASE_DIR / "seed"
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'inspections.db'}")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me-please-0123456789")
JWT_ALG = "HS256"
JWT_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "480"))
CORS_ORIGINS = [o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o]
SIM_AUTOSTART = os.getenv("SIM_AUTOSTART", "1") == "1"
SIM_INTERVAL_S = float(os.getenv("SIM_INTERVAL_S", "4"))
# Demo users (documented in the README; override with env in any shared deployment).
DEMO_USERS = [
    {"username": "admin", "password": os.getenv("DEMO_ADMIN_PASSWORD", "Planta-Admin-2026"), "role": "admin", "name": "Administrador"},
    {"username": "operador", "password": os.getenv("DEMO_OPERATOR_PASSWORD", "Planta-Operador-2026"), "role": "operator", "name": "Operador PC10"},
]
