"""
Diagonales Intelligence API — FastAPI
Endpoints principales de la plataforma.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus, urlparse
import httpx
from bs4 import BeautifulSoup
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


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "diagonales-intelligence",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ─── FRONTEND ─────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    path = os.path.join(FRONTEND_DIR, "templates", "index.html")
    return FileResponse(path) if os.path.exists(path) else HTMLResponse("<h1>Diagonales Intelligence</h1>")


@app.get("/radiografia", response_class=HTMLResponse)
def radiografia_page():
    path = os.path.join(FRONTEND_DIR, "templates", "radiografia.html")
    return FileResponse(path)


@app.get("/buscador", response_class=HTMLResponse)
def buscador_page():
    path = os.path.join(FRONTEND_DIR, "templates", "buscador.html")
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


class BusquedaOsintRequest(BaseModel):
    consulta: str
    identificador: Optional[str] = None
    tipo: str = "persona"


class InformeComercialRequest(BaseModel):
    nombre: str
    identificador: Optional[str] = None
    provincia: Optional[str] = None
    tipo: str = "persona"
    max_resultados_por_fuente: int = 5


SOURCE_CATALOG = [
    {"id": "bora", "nombre": "Boletin Oficial BORA", "categoria": "sociedades", "url": "https://www.boletinoficial.gob.ar/"},
    {"id": "bora_segunda", "nombre": "BORA Segunda Seccion", "categoria": "sociedades", "url": "https://www.boletinoficial.gob.ar/seccion/segunda"},
    {"id": "timeline_bora", "nombre": "Timeline societario BORA", "categoria": "sociedades", "url": "https://timeline.boletinoficial.gob.ar/"},
    {"id": "rns", "nombre": "Registro Nacional de Sociedades", "categoria": "sociedades", "url": "https://www.argentina.gob.ar/justicia/registro-nacional-sociedades"},
    {"id": "igj", "nombre": "IGJ", "categoria": "sociedades", "url": "https://www.argentina.gob.ar/justicia/igj"},
    {"id": "bcra", "nombre": "BCRA Central de Deudores", "categoria": "crediticia", "url": "https://www.bcra.gob.ar/BCRAyVos/Situacion_Crediticia.asp"},
    {"id": "arca", "nombre": "ARCA", "categoria": "fiscal", "url": "https://www.arca.gob.ar/"},
    {"id": "sssalud", "nombre": "SSSalud", "categoria": "laboral", "url": "https://www.sssalud.gob.ar/"},
    {"id": "anses", "nombre": "ANSES", "categoria": "laboral", "url": "https://www.anses.gob.ar/"},
    {"id": "srt", "nombre": "SRT", "categoria": "laboral", "url": "https://www.srt.gob.ar/"},
    {"id": "pjn", "nombre": "PJN", "categoria": "judicial", "url": "https://www.pjn.gov.ar/"},
    {"id": "csjn", "nombre": "CSJN", "categoria": "judicial", "url": "https://www.csjn.gov.ar/"},
    {"id": "compras", "nombre": "Compras publicas", "categoria": "licitaciones", "url": "https://www.compras.gob.ar/"},
    {"id": "diputados", "nombre": "Diputados Nacionales", "categoria": "legisladores", "url": "https://www.diputados.gov.ar/diputados/"},
    {"id": "senado", "nombre": "Senado Nacional", "categoria": "legisladores", "url": "https://www.senado.gob.ar/senadores/listado/completo"},
    {"id": "directorio_legislativo", "nombre": "Directorio Legislativo", "categoria": "legisladores", "url": "https://directoriodirecto.org/"},
    {"id": "clarin", "nombre": "Clarin", "categoria": "medios", "url": "https://www.clarin.com/"},
    {"id": "lanacion", "nombre": "La Nacion", "categoria": "medios", "url": "https://www.lanacion.com.ar/"},
    {"id": "infobae", "nombre": "Infobae", "categoria": "medios", "url": "https://www.infobae.com/"},
    {"id": "pagina12", "nombre": "Pagina 12", "categoria": "medios", "url": "https://www.pagina12.com.ar/"},
    {"id": "ambito", "nombre": "Ambito", "categoria": "medios", "url": "https://www.ambito.com/"},
    {"id": "perfil", "nombre": "Perfil", "categoria": "medios", "url": "https://www.perfil.com/"},
    {"id": "cronista", "nombre": "El Cronista", "categoria": "medios", "url": "https://www.cronista.com/"},
    {"id": "bo_buenos_aires", "nombre": "Boletin Oficial Buenos Aires", "categoria": "boletines_provinciales", "url": "https://boletinoficial.gba.gob.ar/"},
    {"id": "dppj_buenos_aires", "nombre": "DPPJ Buenos Aires", "categoria": "sociedades", "url": "https://www.gba.gob.ar/dppj"},
    {"id": "bo_caba", "nombre": "Boletin Oficial CABA", "categoria": "boletines_provinciales", "url": "https://boletinoficial.buenosaires.gob.ar/"},
    {"id": "bo_cordoba", "nombre": "Boletin Oficial Cordoba", "categoria": "boletines_provinciales", "url": "https://boletinoficial.cba.gov.ar/"},
    {"id": "ipj_cordoba", "nombre": "IPJ Cordoba", "categoria": "sociedades", "url": "https://ipj.cba.gov.ar/"},
    {"id": "bo_santafe", "nombre": "Boletin Oficial Santa Fe", "categoria": "boletines_provinciales", "url": "https://www.santafe.gob.ar/boletinoficial/"},
    {"id": "bo_mendoza", "nombre": "Boletin Oficial Mendoza", "categoria": "boletines_provinciales", "url": "https://boletinoficial.mendoza.gov.ar/"},
    {"id": "dpj_mendoza", "nombre": "DPJ Mendoza", "categoria": "sociedades", "url": "https://atencionciudadana.mendoza.gob.ar/dpj/"},
    {"id": "bo_tucuman", "nombre": "Boletin Oficial Tucuman", "categoria": "boletines_provinciales", "url": "https://boletin.tucuman.gov.ar/"},
    {"id": "bo_salta", "nombre": "Boletin Oficial Salta", "categoria": "boletines_provinciales", "url": "https://boletinoficialsalta.gob.ar/"},
    {"id": "pj_salta", "nombre": "Personas Juridicas Salta", "categoria": "sociedades", "url": "https://personasjuridicas.salta.gob.ar/"},
    {"id": "bo_chaco", "nombre": "Boletin Oficial Chaco", "categoria": "boletines_provinciales", "url": "https://boletin.chaco.gob.ar/"},
    {"id": "pj_chaco", "nombre": "Personas Juridicas Chaco", "categoria": "sociedades", "url": "https://personasjuridicas.chaco.gov.ar"},
    {"id": "bo_misiones", "nombre": "Boletin Oficial Misiones", "categoria": "boletines_provinciales", "url": "https://www.boletin.misiones.gov.ar/"},
    {"id": "pj_misiones", "nombre": "Personas Juridicas Misiones", "categoria": "sociedades", "url": "https://personasjuridicas.misiones.gob.ar/"},
    {"id": "bo_corrientes", "nombre": "Boletin Oficial Corrientes", "categoria": "boletines_provinciales", "url": "https://boletinoficial.corrientes.gob.ar/"},
    {"id": "bo_entrerios", "nombre": "Boletin Oficial Entre Rios", "categoria": "boletines_provinciales", "url": "https://www.entrerios.gov.ar/boletin/"},
    {"id": "pj_entrerios", "nombre": "Personas Juridicas Entre Rios", "categoria": "sociedades", "url": "https://portal.entrerios.gov.ar/seguridadyjusticia/personasjuridicas/inicio"},
    {"id": "bo_formosa", "nombre": "Boletin Oficial Formosa", "categoria": "boletines_provinciales", "url": "https://www.formosa.gob.ar/boletinoficial"},
    {"id": "pj_formosa", "nombre": "Personas Juridicas Formosa", "categoria": "sociedades", "url": "https://www.formosa.gob.ar/personasjuridicas"},
    {"id": "bo_jujuy", "nombre": "Boletin Oficial Jujuy", "categoria": "boletines_provinciales", "url": "https://boletinoficial.jujuy.gob.ar/"},
    {"id": "bo_lapampa", "nombre": "Boletin Oficial La Pampa", "categoria": "boletines_provinciales", "url": "https://boletinoficial.lapampa.gob.ar/"},
    {"id": "pj_lapampa", "nombre": "Personas Juridicas La Pampa", "categoria": "sociedades", "url": "https://dgpersonasjuridicas.lapampa.gob.ar/"},
    {"id": "bo_larioja", "nombre": "Boletin Oficial La Rioja", "categoria": "boletines_provinciales", "url": "https://www.boletinoflarioja.com.ar/"},
    {"id": "bo_neuquen", "nombre": "Boletin Oficial Neuquen", "categoria": "boletines_provinciales", "url": "https://boletinoficial.neuquen.gov.ar/"},
    {"id": "pj_neuquen", "nombre": "Personas Juridicas Neuquen", "categoria": "sociedades", "url": "https://personasjuridicas.neuquen.gov.ar/"},
    {"id": "bo_rionegro", "nombre": "Boletin Oficial Rio Negro", "categoria": "boletines_provinciales", "url": "https://boletinoficial.rionegro.gov.ar/"},
    {"id": "pj_rionegro", "nombre": "Personas Juridicas Rio Negro", "categoria": "sociedades", "url": "https://personasjuridicas.rionegro.gov.ar/"},
    {"id": "bo_sanjuan", "nombre": "Boletin Oficial San Juan", "categoria": "boletines_provinciales", "url": "https://boletinoficial.sanjuan.gob.ar/"},
    {"id": "bo_sanluis", "nombre": "Boletin Oficial San Luis", "categoria": "boletines_provinciales", "url": "https://boletinoficial.sanluis.gov.ar/"},
    {"id": "bo_santacruz", "nombre": "Boletin Oficial Santa Cruz", "categoria": "boletines_provinciales", "url": "https://boletinoficial.santacruz.gob.ar/"},
    {"id": "bo_santiago", "nombre": "Boletin Oficial Santiago del Estero", "categoria": "boletines_provinciales", "url": "https://www.boletinsde.gov.ar/"},
    {"id": "bo_tdf", "nombre": "Boletin Oficial Tierra del Fuego", "categoria": "boletines_provinciales", "url": "https://www.tierradelfuego.gob.ar/boletin-oficial/"},
    {"id": "leg_caba", "nombre": "Legislatura CABA", "categoria": "legisladores", "url": "https://www.legislatura.gob.ar/posts/legisladores"},
    {"id": "dip_pba", "nombre": "Diputados Buenos Aires", "categoria": "legisladores", "url": "https://www.hcdiputados-ba.gov.ar/"},
    {"id": "sen_pba", "nombre": "Senado Buenos Aires", "categoria": "legisladores", "url": "https://www.senado-ba.gov.ar/"},
    {"id": "leg_cordoba", "nombre": "Legislatura Cordoba", "categoria": "legisladores", "url": "https://legislaturacba.gob.ar/legisladores/"},
    {"id": "youtube_tn", "nombre": "TN YouTube", "categoria": "medios_audiovisuales", "url": "https://www.youtube.com/@todonoticias"},
    {"id": "youtube_c5n", "nombre": "C5N YouTube", "categoria": "medios_audiovisuales", "url": "https://www.youtube.com/@c5n"},
    {"id": "youtube_destape", "nombre": "El Destape YouTube", "categoria": "medios_audiovisuales", "url": "https://www.youtube.com/@eldestapetv"},
]


@app.post("/api/osint/busqueda")
def busqueda_osint(req: BusquedaOsintRequest):
    """
    Genera un tablero de busqueda web OSINT sin depender del entorno local.
    """
    consulta = req.consulta.strip()
    if not consulta:
        raise HTTPException(400, "La consulta es obligatoria")

    normalizado = normalizar_identificador(req.identificador or "") if req.identificador else None
    cuil_principal = None
    if normalizado:
        cuiles = normalizado.get("cuils_derivados") or []
        cuil_principal = cuiles[0] if cuiles else None

    dorks = generar_dorks(consulta, cuil_principal)
    extra = {
        "empresas": [
            f'"{consulta}" CUIT OR sociedad OR directorio',
            f'site:boletinoficial.gob.ar "{consulta}"',
            f'site:compras.gob.ar "{consulta}"',
        ],
        "dominios": [
            f'"{consulta}" site:.ar',
            f'"{consulta}" "whois" OR "dominio"',
        ],
    }


@app.post("/api/informe/comercial")
def informe_comercial(req: InformeComercialRequest):
    """
    Ejecuta busquedas OSINT publicas y devuelve un informe estructurado con evidencia,
    confianza y grafo. No evade captchas, logins, paywalls ni fuentes privadas.
    """
    nombre = req.nombre.strip()
    if not nombre:
        raise HTTPException(400, "El nombre es obligatorio")

    normalizado = normalizar_identificador(req.identificador or "") if req.identificador else None
    cuiles = (normalizado or {}).get("cuils_derivados", [])

    evidencias = []
    fuentes = []
    hallazgos = []

    # BCRA es la consulta oficial directa disponible sin captcha.
    bcra_resultados = []
    for cuil in cuiles[:3]:
        res = consultar_deudas(cuil)
        bcra_resultados.append(res)
        evidencia = {
            "fuente": "BCRA Central de Deudores",
            "categoria": "crediticia",
            "url": "https://api.bcra.gob.ar/CentralDeDeudores/v1.0",
            "titulo": f"Consulta BCRA {cuil}",
            "extracto": f"Estado: {res.get('estado')}; deudas: {len(res.get('deudas', []))}; cheques: {len(res.get('cheques_rechazados', []))}",
            "coincidencia": "identificador",
            "confianza": "alta" if res.get("estado") not in ("error", "timeout", "error_api") else "media",
        }
        evidencias.append(evidencia)

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {
            executor.submit(_buscar_fuente, nombre, source, req.max_resultados_por_fuente): source
            for source in SOURCE_CATALOG
        }
        for future in as_completed(futures):
            source = futures[future]
            resultados = future.result()
            fuentes.append({
                "id": source["id"],
                "nombre": source["nombre"],
                "categoria": source["categoria"],
                "url": source["url"],
                "resultados": len(resultados),
                "estado": "con_hallazgos" if resultados else "sin_hallazgos",
            })
            evidencias.extend(resultados)

    categorias = {}
    for ev in evidencias:
        categorias.setdefault(ev["categoria"], 0)
        categorias[ev["categoria"]] += 1

    riesgo_crediticio = "indeterminado"
    if bcra_resultados:
        riesgos = [clasificar_riesgo(r) for r in bcra_resultados]
        if "alto" in riesgos:
            riesgo_crediticio = "alto"
        elif "medio" in riesgos:
            riesgo_crediticio = "medio"
        elif "bajo" in riesgos:
            riesgo_crediticio = "bajo"

    verificadas = [e for e in evidencias if e.get("confianza") == "alta"]
    indicios = [e for e in evidencias if e.get("confianza") in ("media", "baja")]
    fuentes_con_hallazgos = len({e.get("fuente") for e in evidencias})
    confiabilidad_global = _confiabilidad_global(evidencias, bool(cuiles))

    hallazgos.append({
        "titulo": "Identidad normalizada",
        "valor": (normalizado or {}).get("formateado") or "sin identificador",
        "confianza": "alta" if cuiles else "media",
        "detalle": f"CUIL/CUIT derivados o informados: {len(cuiles)}",
    })
    hallazgos.append({
        "titulo": "Riesgo crediticio BCRA",
        "valor": riesgo_crediticio,
        "confianza": "alta" if bcra_resultados else "baja",
        "detalle": "Basado solo en API publica BCRA cuando hay CUIL/CUIT/DNI suficiente.",
    })
    hallazgos.append({
        "titulo": "Cobertura OSINT",
        "valor": f"{len(evidencias)} evidencias / {len(SOURCE_CATALOG)} fuentes",
        "confianza": confiabilidad_global,
        "detalle": f"Fuentes con hallazgos: {fuentes_con_hallazgos}. Verificadas: {len(verificadas)}. Indicios: {len(indicios)}.",
    })
    hallazgos.append({
        "titulo": "Confiabilidad integral",
        "valor": confiabilidad_global,
        "confianza": confiabilidad_global,
        "detalle": "Alta requiere identificador oficial o coincidencias fuertes en varias fuentes independientes.",
    })

    grafo = _construir_grafo(nombre, evidencias, cuiles, categorias)

    return {
        "target": {
            "nombre": nombre,
            "identificador": req.identificador,
            "provincia": req.provincia,
            "tipo": req.tipo,
            "normalizado": normalizado,
        },
        "resumen": {
            "fecha": datetime.now(timezone.utc).isoformat(),
            "fuentes_consultadas": len(SOURCE_CATALOG) + (1 if cuiles else 0),
            "evidencias": len(evidencias),
            "categorias": categorias,
            "riesgo_crediticio": riesgo_crediticio,
            "fuentes_con_hallazgos": fuentes_con_hallazgos,
            "evidencias_verificadas": len(verificadas),
            "indicios": len(indicios),
            "confiabilidad_global": confiabilidad_global,
        },
        "hallazgos": hallazgos,
        "fuentes": fuentes,
        "evidencias": evidencias,
        "evidencias_verificadas": verificadas,
        "indicios": indicios,
        "grafo": grafo,
        "limitaciones": [
            "ARCA, ANSES, SSSalud, SRT, IGJ y algunos registros pueden requerir captcha, login o consulta manual para datos completos.",
            "El informe separa evidencia encontrada de certeza plena; la certeza exige coincidencia por identificador oficial o dos fuentes independientes.",
            "No se consultan bases privadas como Nosis ni fuentes con paywall o acceso restringido.",
        ],
    }


def _dominio(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _buscar_fuente(nombre: str, source: dict, limite: int) -> list[dict]:
    evidencias = []
    seen = set()
    try:
        headers = {"User-Agent": "Diagonales-Intelligence/1.0"}
        for query in _queries_para_fuente(nombre, source):
            url = "https://duckduckgo.com/html/?q=" + quote_plus(query)
            r = httpx.get(url, headers=headers, timeout=8, follow_redirects=True)
            if r.status_code >= 400:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select(".result")[:limite]:
                title_el = item.select_one(".result__title a")
                snippet_el = item.select_one(".result__snippet")
                if not title_el:
                    continue
                title = re.sub(r"\s+", " ", title_el.get_text(" ", strip=True))
                href = title_el.get("href") or source["url"]
                if href in seen:
                    continue
                seen.add(href)
                snippet = re.sub(r"\s+", " ", snippet_el.get_text(" ", strip=True)) if snippet_el else ""
                confianza, score, razon = _score_evidencia(nombre, title, snippet, source, query)
                evidencias.append({
                    "fuente": source["nombre"],
                    "categoria": source["categoria"],
                    "url": href,
                    "titulo": title,
                    "extracto": snippet[:700],
                    "coincidencia": razon,
                    "confianza": confianza,
                    "score": score,
                    "query": query,
                })
    except Exception:
        return []
    evidencias.sort(key=lambda e: e.get("score", 0), reverse=True)
    return evidencias[:limite]


def _queries_para_fuente(nombre: str, source: dict) -> list[str]:
    dominio = _dominio(source["url"])
    q = f'"{nombre}"'
    cat = source["categoria"]
    terms = {
        "sociedades": ["CUIT", "sociedad", "S.A.", "S.R.L.", "SAS", "gerente", "directorio", "constitucion", "edictos"],
        "boletines_provinciales": ["boletin oficial", "edicto", "resolucion", "decreto", "licitacion", "sociedad"],
        "judicial": ["causa", "expediente", "fallo", "sentencia", "procesado", "demandado"],
        "licitaciones": ["licitacion", "contratacion", "adjudicacion", "proveedor", "orden de compra"],
        "legisladores": ["diputado", "senador", "legislador", "bloque", "mandato"],
        "medios": ["denuncia", "investigacion", "empresa", "funcionario", "causa", "licitacion"],
        "medios_audiovisuales": ["entrevista", "denuncia", "informe", "politica", "economia"],
        "crediticia": ["deudores", "cheques rechazados", "situacion crediticia"],
        "fiscal": ["CUIT", "constancia", "actividad", "domicilio fiscal"],
        "laboral": ["obra social", "empleador", "ART", "aportes"],
    }.get(cat, ["Argentina"])
    queries = [f"site:{dominio} {q}"]
    queries.extend(f"site:{dominio} {q} {term}" for term in terms[:5])
    return queries


def _tokens(text: str) -> set[str]:
    return {t for t in re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ]", " ", text).lower().split() if len(t) > 2}


def _score_evidencia(nombre: str, title: str, snippet: str, source: dict, query: str) -> tuple[str, int, str]:
    haystack = f"{title} {snippet}".lower()
    nombre_tokens = _tokens(nombre)
    hit_tokens = _tokens(haystack)
    overlap = len(nombre_tokens & hit_tokens)
    score = overlap * 18
    if nombre.lower() in haystack:
        score += 45
    if source["categoria"] in ("sociedades", "crediticia", "judicial", "boletines_provinciales"):
        score += 10
    if any(term in haystack for term in ["cuit", "cuil", "dni", "boletin", "sociedad", "expediente", "deudor", "licitacion"]):
        score += 12
    if score >= 70:
        return "alta", min(score, 100), "coincidencia fuerte en fuente prioritaria"
    if score >= 35:
        return "media", score, "coincidencia parcial o contextual"
    return "baja", score, "indicio debil; requiere revision"


def _confiabilidad_global(evidencias: list[dict], tiene_identificador: bool) -> str:
    altas = [e for e in evidencias if e.get("confianza") == "alta"]
    categorias_altas = {e.get("categoria") for e in altas}
    fuentes_altas = {e.get("fuente") for e in altas}
    if tiene_identificador and len(altas) >= 1:
        return "alta"
    if len(fuentes_altas) >= 3 and len(categorias_altas) >= 2:
        return "alta"
    if len(evidencias) >= 3:
        return "media"
    return "baja"


def _construir_grafo(nombre: str, evidencias: list[dict], cuiles: list[str], categorias: dict) -> dict:
    nodes = [{"id": "target", "label": nombre, "type": "persona", "score": 100}]
    edges = []
    for cuil in cuiles[:3]:
        node_id = f"id-{cuil}"
        nodes.append({"id": node_id, "label": cuil, "type": "identificador", "score": 90})
        edges.append({"from": "target", "to": node_id, "label": "identificador", "confidence": "alta"})
    for cat, count in categorias.items():
        node_id = f"cat-{cat}"
        nodes.append({"id": node_id, "label": f"{cat} ({count})", "type": "categoria", "score": min(90, 30 + count * 10)})
        edges.append({"from": "target", "to": node_id, "label": "evidencia", "confidence": "media"})
    for i, ev in enumerate(evidencias[:30]):
        node_id = f"ev-{i}"
        nodes.append({"id": node_id, "label": ev["fuente"], "type": "fuente", "score": 60})
        edges.append({"from": f"cat-{ev['categoria']}", "to": node_id, "label": ev["confianza"], "confidence": ev["confianza"]})
    return {"nodes": nodes, "edges": edges}
    if req.tipo in ("empresa", "dominio"):
        dorks.update(extra)

    def google_url(q: str) -> str:
        from urllib.parse import quote_plus
        return "https://www.google.com/search?q=" + quote_plus(q)

    enlaces = [
        {"titulo": "Google", "url": google_url(consulta), "tipo": "busqueda"},
        {"titulo": "Google News", "url": "https://news.google.com/search?q=" + consulta.replace(" ", "+"), "tipo": "medios"},
        {"titulo": "LinkedIn", "url": google_url(f'site:linkedin.com "{consulta}"'), "tipo": "redes"},
        {"titulo": "X/Twitter", "url": google_url(f'site:x.com "{consulta}"'), "tipo": "redes"},
        {"titulo": "Boletin Oficial", "url": google_url(f'site:boletinoficial.gob.ar "{consulta}"'), "tipo": "argentina"},
        {"titulo": "Poder Judicial", "url": google_url(f'site:pjn.gov.ar "{consulta}"'), "tipo": "judicial"},
        {"titulo": "Compras publicas", "url": google_url(f'site:compras.gob.ar "{consulta}"'), "tipo": "contrataciones"},
    ]

    return {
        "consulta": consulta,
        "tipo": req.tipo,
        "normalizado": normalizado,
        "dorks": dorks,
        "enlaces": enlaces,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


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
