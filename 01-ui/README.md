# UI (req. 1)

React 19 + Vite + TypeScript + Tailwind v4 (frontend) · FastAPI + SQLAlchemy + SQLite (backend). Ver la sección 5 del README principal.

```
backend/app/{main,api,sim,catalog,models,security,broker,config,db}.py   API, simulador, catálogo, SSE
backend/seed/                      pool de imágenes demo + manifest.json (versionado, 9 MB)
backend/tests/                     pytest (9)
frontend/src/{pages,components,lib}  Login, Dashboard, Station, History, Catalog
assets-gen/                        generador de imágenes (uv): geometric.py, procedural.py, diffusion.py, build_seed.py
tools/screenshots.mjs              capturas + comprobaciones por CDP (Chromium headless, sin Playwright)
```

Comandos: `./run.sh` · `cd backend && uv run pytest -q` · `cd frontend && pnpm typecheck && pnpm build` · `node tools/screenshots.mjs`.

API (todas bajo `/api`, Bearer JWT salvo login): `POST /auth/login`, `GET /auth/me`, `/catalog`, `/stations`, `/inspections` (filtros `station,defect,verdict,date_from,date_to,q,sort,page,page_size`), `/inspections/{id}`, `POST /inspections/manual`, `/stats`, `GET /stream?token=` (SSE), `/simulator`, `POST /simulator/start|stop` (admin).
