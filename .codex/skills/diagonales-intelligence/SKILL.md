---
name: diagonales-intelligence
description: Operate, deploy, debug, and extend the Consultora Diagonales intelligence platform. Use when working with diagonales-intelligence, SCRAPING DATOS, OSINT searches, FastAPI endpoints, GitHub Pages frontend, BCRA/CUIL radiografia, RSS/YouTube scraping, sentiment reports, objetivos, scheduler runs, production deployment, or installation of this skill in Claude/ChatGPT/Codex.
---

# Diagonales Intelligence

## Quick Start

Use this skill as the operating guide for the two local systems:

- `F:\001COnsultora politica\diagonales-intelligence`: FastAPI API, dashboard, radiografia 360, OSINT web frontend.
- `F:\001COnsultora politica\SCRAPING DATOS`: RSS/YouTube scraping, sentiment analysis, Excel/DOCX/HTML reports.

Before changing code, inspect the relevant repo state with `git status --short --branch`, read nearby files, and keep changes scoped.

## Task Router

- For endpoint, route, schema, deployment, or frontend work, read `references/platform.md`.
- For searches, dorks, BCRA, CUIL/CUIT derivation, and radiografia workflows, read `references/osint-workflows.md`.
- For scraping, scheduler runs, objetivos, reports, and YouTube API keys, read `references/scraping-workflows.md`.
- For installing this skill into Claude, ChatGPT/Codex, or exporting a ZIP, read `references/install.md`.

## Core Commands

Run from `F:\001COnsultora politica\diagonales-intelligence` unless noted:

```powershell
python run_dashboard.py
python -m compileall backend run.py run_dashboard.py
python -c "from backend.api.main import app; print([r.path for r in app.routes])"
```

Run from `F:\001COnsultora politica\SCRAPING DATOS`:

```powershell
python scheduler.py --ahora
python gestionar.py agregar
python scrapers/generador_reportes.py
```

## GitHub Publishing

The intended remote is `https://github.com/consultoradiagonales/diagonales-intelligence.git`. If push returns `Repository not found`, verify the repo exists and the current GitHub credentials have access before changing remotes.

Use GitHub Pages from `main` and `/docs` for the static OSINT frontend.

## Safety

Do not commit `.env`, `config/api_keys.json`, local `.db` files, exports, logs, or secrets. Keep CORS permissive only when the API is intentionally public or fronted by another access-control layer.
