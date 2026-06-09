# Platform Reference

## Repository

Local path: `F:\001COnsultora politica\diagonales-intelligence`

Main components:

- `backend/api/main.py`: FastAPI app, CORS, frontend routes, API endpoints.
- `backend/analyzers/identidad.py`: DNI/CUIL/CUIT normalization, AFIP modulo 11 validation, dork generation.
- `backend/scrapers/bcra.py`: BCRA Central de Deudores integration and credit-risk classification.
- `frontend/templates/index.html`: dashboard.
- `frontend/templates/radiografia.html`: identity/radiografia UI.
- `frontend/templates/buscador.html`: integrated OSINT web frontend.
- `docs/index.html`: static OSINT frontend for GitHub Pages.
- `run_dashboard.py`: dashboard launcher on port 8000.

## API Surface

Important endpoints:

- `GET /`: dashboard HTML.
- `GET /radiografia`: radiografia UI.
- `GET /buscador`: OSINT frontend.
- `POST /api/osint/busqueda`: dorks and direct links for web searches.
- `POST /api/radiografia/identidad`: identifier normalization, BCRA lookups, dorks.
- `GET /api/objetivos`, `POST /api/objetivos`, `PATCH /api/objetivos/{id}/toggle`: objetivos.
- `GET /api/humor-social/{objetivo_id}`: social mood summary.
- `GET /api/humor-social/{objetivo_id}/comentarios-calientes`: high-engagement negative comments.
- `GET /api/humor-social/{objetivo_id}/articulos-recientes`: recent articles.
- `POST /api/scraping/rss`, `POST /api/scraping/youtube`, `POST /api/analizar`: manual background tasks.
- `GET /api/stats`: global counts.

## Frontend Deployment

For GitHub Pages:

1. Keep `docs/index.html` self-contained.
2. In GitHub repo settings, set Pages source to branch `main`, folder `/docs`.
3. If the FastAPI backend is deployed, paste its public base URL into the frontend API field.
4. If no API is available, the page still generates Google-based OSINT dorks in static mode.

## Verification

Use these checks after edits:

```powershell
python -m compileall backend run.py run_dashboard.py
python -c "from backend.api.main import app; print([r.path for r in app.routes if 'osint' in r.path or r.path == '/buscador'])"
python -c "from fastapi.testclient import TestClient; from backend.api.main import app; c=TestClient(app); r=c.post('/api/osint/busqueda', json={'consulta':'Consultora Diagonales','tipo':'empresa'}); print(r.status_code, r.json()['consulta'])"
```
