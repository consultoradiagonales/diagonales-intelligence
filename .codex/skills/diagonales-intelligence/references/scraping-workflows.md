# Scraping Workflows

## Repository

Local path: `F:\001COnsultora politica\SCRAPING DATOS`

Capabilities:

- RSS scraping across 19 portals.
- YouTube scraping and comments through YouTube Data API.
- Sentiment analysis.
- Reports in Excel, DOCX, HTML, and console formats.
- Scheduler for immediate or recurring cycles.

## Main Commands

```powershell
python start_api.py
python scheduler.py --ahora
python scheduler.py --rss
python scheduler.py --yt
python gestionar.py agregar
python gestionar.py listar
python scrapers/generador_reportes.py
```

## YouTube API Key

Store the key in `config/api_keys.json`. Do not commit this file.

Expected `.gitignore` behavior:

- Ignore `.env`.
- Ignore `config/api_keys.json`.
- Ignore local databases, logs, and generated exports.

## Objetivos

Create the first 3-5 objetivos with `python gestionar.py agregar`. Use stable IDs, clear names, target type, and keyword lists that include common spelling variants.

Before a production cycle:

1. Confirm API keys exist.
2. List objetivos.
3. Run RSS-only if testing ingestion.
4. Run YouTube-only if testing API quota.
5. Run full cycle with `python scheduler.py --ahora`.
6. Generate or inspect reports.

## Troubleshooting

- If YouTube returns auth/quota errors, verify key and API enablement in Google Cloud.
- If RSS returns few results, inspect objective keywords and feed availability.
- If reports are empty, verify scraping inserted content and sentiment analysis ran.
