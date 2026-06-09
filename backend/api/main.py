"""
Diagonales Intelligence API — FastAPI
Endpoints principales de la plataforma.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from ..db.database import get_db, init_db
from ..db.models import (
    Objetivo, Contenido, Sentimiento, ResumenDiario,
    Comentario, SentimientoComentario, Engagement, ConsultaIdentidad
)
from ..analyzers.identidad import normalizar_identificador, derivar_cuils, generar_dorks
from ..scrapers.bcra import consultar_deudas, clasificar_riesgo

app = FastAPI(
    title="Diagonales Intelligence",
    description="Plataforma de inteligencia política y análisis de humor social",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir frontend estático
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")


@app.on_event("startup")
def startup():
    init_db()


# ─── FRONTEND ─────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    path = os.path.join(FRONTEND_DIR, "templates", "index.html")
    return FileResponse(path) if os.path.exists(path) else HTMLResponse("<h1>Diagonales Intelligence</h1>")


@app.get("/radiografia", response_class=HTMLResponse)
def radiografia_page():
    path = os.path.join(FRONTEND_DIR, "templates", "radiografia.html")
    return FileResponse(path)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    path = os.path.join(FRONTEND_DIR, "templates", "dashboard.html")
    return FileResponse(path)


# ─── OBJETIVOS ────────────────────────────────────────────────

class ObjetivoCreate(BaseModel):
    id:       str
    nombre:   str
    tipo:     str  # candidato|empresa|funcionario
    keywords: list[str]
    activo:   bool = True
    redes:    dict = {}


@app.get("/api/objetivos")
def listar_objetivos(db: Session = Depends(get_db)):
    objs = db.query(Objetivo).all()
    return [_obj_to_dict(o) for o in objs]


@app.post("/api/objetivos")
def crear_objetivo(data: ObjetivoCreate, db: Session = Depends(get_db)):
    if db.query(Objetivo).filter(Objetivo.id == data.id).first():
        raise HTTPException(400, "Ya existe un objetivo con ese ID")
    obj = Objetivo(
        id=data.id, nombre=data.nombre, tipo=data.tipo,
        activo=data.activo,
        keywords=json.dumps(data.keywords, ensure_ascii=False),
        redes_json=json.dumps(data.redes, ensure_ascii=False)
    )
    db.add(obj)
    db.commit()
    return _obj_to_dict(obj)


@app.patch("/api/objetivos/{obj_id}/toggle")
def toggle_objetivo(obj_id: str, db: Session = Depends(get_db)):
    obj = db.query(Objetivo).filter(Objetivo.id == obj_id).first()
    if not obj:
        raise HTTPException(404)
    obj.activo = not obj.activo
    db.commit()
    return {"id": obj_id, "activo": obj.activo}


# ─── HUMOR SOCIAL ─────────────────────────────────────────────

@app.get("/api/humor-social/{objetivo_id}")
def humor_social(objetivo_id: str, dias: int = 7, db: Session = Depends(get_db)):
    """Resumen de humor social para un objetivo en los últimos N días."""
    obj = db.query(Objetivo).filter(Objetivo.id == objetivo_id).first()
    if not obj:
        raise HTTPException(404)

    fecha_desde = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%d")

    resumenes = (
        db.query(ResumenDiario)
        .filter(ResumenDiario.objetivo_id == objetivo_id)
        .filter(ResumenDiario.fecha >= fecha_desde)
        .order_by(ResumenDiario.fecha)
        .all()
    )

    # Sentimiento total del período
    conteos = (
        db.query(Sentimiento.sentimiento, func.count().label("n"))
        .join(Contenido, Contenido.id == Sentimiento.contenido_id)
        .filter(Contenido.objetivo_id == objetivo_id)
        .filter(Sentimiento.fecha_analisis >= datetime.now(timezone.utc) - timedelta(days=dias))
        .group_by(Sentimiento.sentimiento)
        .all()
    )
    d = {r.sentimiento: r.n for r in conteos}
    total = sum(d.values()) or 1

    # Top fuentes
    fuentes = (
        db.query(Contenido.fuente_nombre, func.count().label("n"))
        .filter(Contenido.objetivo_id == objetivo_id)
        .filter(Contenido.fecha_scrape >= datetime.now(timezone.utc) - timedelta(days=dias))
        .group_by(Contenido.fuente_nombre)
        .order_by(desc("n"))
        .limit(10).all()
    )

    return {
        "objetivo": _obj_to_dict(obj),
        "periodo_dias": dias,
        "total_menciones": total,
        "sentimiento_global": {
            "positivo": round(d.get("POS", 0) / total * 100, 1),
            "negativo": round(d.get("NEG", 0) / total * 100, 1),
            "neutro":   round(d.get("NEU", 0) / total * 100, 1),
        },
        "evolucion_diaria": [
            {
                "fecha": r.fecha,
                "menciones": r.total_menciones,
                "positivo": r.pct_positivo,
                "negativo": r.pct_negativo,
                "neutro": r.pct_neutro,
                "engagement": r.total_engagement
            } for r in resumenes
        ],
        "top_fuentes": [{"fuente": f.fuente_nombre, "menciones": f.n} for f in fuentes]
    }


@app.get("/api/humor-social/{objetivo_id}/comentarios-calientes")
def comentarios_calientes(objetivo_id: str, limite: int = 20, db: Session = Depends(get_db)):
    """Comentarios negativos con más engagement — los que más calentaron."""
    rows = (
        db.query(Comentario, SentimientoComentario)
        .join(SentimientoComentario, SentimientoComentario.comentario_id == Comentario.id)
        .filter(Comentario.objetivo_id == objetivo_id)
        .filter(SentimientoComentario.sentimiento == "NEG")
        .order_by(desc(Comentario.likes), desc(SentimientoComentario.score_neg))
        .limit(limite).all()
    )
    return [{
        "texto": c.texto, "autor": c.autor, "fuente": c.fuente_tipo,
        "likes": c.likes, "score_negativo": round(s.score_neg, 3),
        "fecha": c.fecha_pub
    } for c, s in rows]


@app.get("/api/humor-social/{objetivo_id}/articulos-recientes")
def articulos_recientes(objetivo_id: str, limite: int = 30, db: Session = Depends(get_db)):
    rows = (
        db.query(Contenido, Sentimiento)
        .outerjoin(Sentimiento, Sentimiento.contenido_id == Contenido.id)
        .filter(Contenido.objetivo_id == objetivo_id)
        .order_by(desc(Contenido.fecha_scrape))
        .limit(limite).all()
    )
    return [{
        "titulo": c.titulo, "fuente": c.fuente_nombre, "tipo": c.fuente_tipo,
        "url": c.url, "fecha": c.fecha_pub,
        "sentimiento": s.sentimiento if s else None,
        "score_pos": round(s.score_pos, 3) if s else None,
        "score_neg": round(s.score_neg, 3) if s else None,
    } for c, s in rows]


# ─── RADIOGRAFÍA IDENTIDAD ────────────────────────────────────

class ConsultaRequest(BaseModel):
    identificador: str   # DNI o CUIL/CUIT
    nombre:        Optional[str] = None
    objetivo_id:   Optional[str] = None


@app.post("/api/radiografia/identidad")
def radiografia_identidad(req: ConsultaRequest, db: Session = Depends(get_db)):
    """
    Capa 1 de radiografía: identidad, BCRA y search dorks.
    """
    normalizado = normalizar_identificador(req.identificador)

    resultado = {
        "identificador_input": req.identificador,
        "normalizado": normalizado,
        "bcra": [],
        "dorks": {},
        "riesgo_crediticio": "indeterminado",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Consultar BCRA para cada CUIL derivado
    bcra_resultados = []
    for cuil in normalizado.get("cuils_derivados", [])[:3]:
        bcra_res = consultar_deudas(cuil)
        bcra_resultados.append(bcra_res)

        # Guardar en DB
        db.add(ConsultaIdentidad(
            objetivo_id=req.objetivo_id,
            tipo_consulta="bcra",
            identificador=cuil,
            resultado_json=json.dumps(bcra_res, ensure_ascii=False),
            estado=bcra_res["estado"],
            fuente_url="https://api.bcra.gob.ar/CentralDeDeudores/v1.0"
        ))

    db.commit()

    riesgos = [clasificar_riesgo(r) for r in bcra_resultados]
    if "alto" in riesgos:
        riesgo_final = "alto"
    elif "medio" in riesgos:
        riesgo_final = "medio"
    elif all(r == "bajo" for r in riesgos):
        riesgo_final = "bajo"
    else:
        riesgo_final = "indeterminado"

    resultado["bcra"] = bcra_resultados
    resultado["riesgo_crediticio"] = riesgo_final

    if req.nombre:
        cuil_principal = normalizado.get("cuils_derivados", [None])[0]
        resultado["dorks"] = generar_dorks(req.nombre, cuil_principal)

    return resultado


# ─── SCRAPING MANUAL ──────────────────────────────────────────

@app.post("/api/scraping/rss")
def trigger_rss(bg: BackgroundTasks, db: Session = Depends(get_db)):
    from ..scrapers.rss import ejecutar
    bg.add_task(ejecutar, db)
    return {"status": "iniciado", "scraper": "rss"}


@app.post("/api/scraping/youtube")
def trigger_youtube(bg: BackgroundTasks, db: Session = Depends(get_db)):
    from ..scrapers.youtube import ejecutar
    bg.add_task(ejecutar, db)
    return {"status": "iniciado", "scraper": "youtube"}


@app.post("/api/analizar")
def trigger_analizar(bg: BackgroundTasks, db: Session = Depends(get_db)):
    from ..analyzers.sentimiento import analizar_pendiente, calcular_resumen_diario
    def _run(db):
        analizar_pendiente(db)
        calcular_resumen_diario(db)
    bg.add_task(_run, db)
    return {"status": "iniciado", "tarea": "sentimiento"}


# ─── STATS GLOBALES ───────────────────────────────────────────

@app.get("/api/stats")
def stats_globales(db: Session = Depends(get_db)):
    return {
        "total_contenido": db.query(func.count(Contenido.id)).scalar(),
        "total_comentarios": db.query(func.count(Comentario.id)).scalar(),
        "total_analizados": db.query(func.count(Sentimiento.id)).scalar(),
        "objetivos_activos": db.query(func.count(Objetivo.id)).filter(Objetivo.activo == True).scalar(),
        "ultima_actualizacion": db.query(func.max(Contenido.fecha_scrape)).scalar(),
    }


# ─── HELPERS ──────────────────────────────────────────────────

def _obj_to_dict(o: Objetivo) -> dict:
    return {
        "id": o.id, "nombre": o.nombre, "tipo": o.tipo,
        "activo": o.activo,
        "keywords": json.loads(o.keywords or "[]"),
        "redes": json.loads(o.redes_json or "{}"),
        "creado_en": o.creado_en.isoformat() if o.creado_en else None
    }
