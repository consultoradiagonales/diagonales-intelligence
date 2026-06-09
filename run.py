"""
Punto de entrada principal — Diagonales Intelligence Platform
Uso:
    python run.py            → API + scheduler
    python run.py --api      → solo API (puerto 8000)
    python run.py --schedule → solo scheduler
    python run.py --once     → ciclo completo una vez y sale
"""
import sys, os, uvicorn

os.chdir(os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()


def start_api():
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    print(f"[API] http://{host}:{port}")
    uvicorn.run("backend.api.main:app", host=host, port=port, reload=False)


def start_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from backend.db.database import init_db, SessionLocal
    from backend.scrapers import rss, youtube
    from backend.analyzers.sentimiento import analizar_pendiente, calcular_resumen_diario

    init_db()
    tz = os.getenv("TIMEZONE", "America/Argentina/Buenos_Aires")
    scheduler = BlockingScheduler(timezone=tz)

    def run_rss():
        db = SessionLocal(); rss.ejecutar(db); db.close()

    def run_yt():
        db = SessionLocal(); youtube.ejecutar(db); db.close()

    def run_sentiment():
        db = SessionLocal()
        analizar_pendiente(db)
        calcular_resumen_diario(db)
        db.close()

    scheduler.add_job(run_rss, CronTrigger(hour="*/2"), id="rss")
    scheduler.add_job(run_yt,  CronTrigger(hour="6,12,18,23"), id="youtube")
    scheduler.add_job(run_sentiment, CronTrigger(hour="*/1"), id="sentiment")

    print("[Scheduler] RSS cada 2h | YouTube 4x/día | Sentimiento cada hora")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("Scheduler detenido.")


def run_once():
    from backend.db.database import init_db, SessionLocal
    from backend.scrapers import rss, youtube
    from backend.analyzers.sentimiento import analizar_pendiente, calcular_resumen_diario

    init_db()
    db = SessionLocal()
    print("[1/3] RSS...")
    rss.ejecutar(db)
    print("[2/3] YouTube...")
    youtube.ejecutar(db)
    print("[3/3] Sentimiento...")
    analizar_pendiente(db)
    calcular_resumen_diario(db)
    db.close()
    print("Ciclo completo OK.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--once" in args:
        run_once()
    elif "--schedule" in args:
        start_scheduler()
    else:
        # Default: API (en producción usar supervisor para correr los dos)
        start_api()
