"""Scraper RSS — portales de noticias argentinos."""
import feedparser, json, logging, os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..db.models import Contenido, Objetivo

log = logging.getLogger(__name__)

FUENTES = {
    "nacionales": [
        {"nombre": "La Nación",   "url": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/"},
        {"nombre": "Clarín",      "url": "https://www.clarin.com/rss/politica/"},
        {"nombre": "Infobae",     "url": "https://www.infobae.com/feeds/rss/"},
        {"nombre": "Página 12",   "url": "https://www.pagina12.com.ar/rss/portada"},
        {"nombre": "Ámbito",      "url": "https://www.ambito.com/rss/pages/home.xml"},
        {"nombre": "Perfil",      "url": "https://www.perfil.com/feed/"},
        {"nombre": "El Cronista", "url": "https://www.cronista.com/rss/"},
        {"nombre": "TN",          "url": "https://tn.com.ar/rss/"},
        {"nombre": "A24",         "url": "https://www.a24.com/rss/"},
        {"nombre": "IP Digital",  "url": "https://ip.digital/feed/"},
    ],
    "regionales": [
        {"nombre": "La Voz (Cba)",    "url": "https://www.lavoz.com.ar/arc/outboundfeeds/rss/"},
        {"nombre": "Los Andes (Mza)", "url": "https://www.losandes.com.ar/arc/outboundfeeds/rss/"},
        {"nombre": "La Capital (Ros)","url": "https://www.lacapital.com.ar/arc/outboundfeeds/rss/"},
        {"nombre": "La Gaceta (Tuc)", "url": "https://www.lagaceta.com.ar/rss/"},
        {"nombre": "Río Negro",       "url": "https://www.rionegro.com.ar/arc/outboundfeeds/rss/"},
        {"nombre": "El Litoral (SF)", "url": "https://www.ellitoral.com/arc/outboundfeeds/rss/"},
        {"nombre": "El Día (LP)",     "url": "https://www.eldia.com/rss/"},
        {"nombre": "El Tribuno (Sal)","url": "https://www.eltribuno.com/salta/rss"},
        {"nombre": "Norte (Chaco)",   "url": "https://www.diarionorte.com/rss"},
    ]
}


def _menciona(texto: str, keywords: list[str]) -> bool:
    t = texto.lower()
    return any(k.lower() in t for k in keywords)


def ejecutar(db: Session) -> int:
    objetivos = db.query(Objetivo).filter(Objetivo.activo == True).all()
    if not objetivos:
        log.warning("Sin objetivos activos.")
        return 0

    total = 0
    todas = FUENTES["nacionales"] + FUENTES["regionales"]

    for feed_info in todas:
        nombre, url = feed_info["nombre"], feed_info["url"]
        log.info(f"RSS: {nombre}")
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            for entry in feed.entries:
                titulo  = getattr(entry, "title", "") or ""
                resumen = getattr(entry, "summary", "") or ""
                link    = getattr(entry, "link", "") or ""
                autor   = getattr(entry, "author", "") or ""
                pub     = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""
                texto   = f"{titulo} {resumen}"

                for obj in objetivos:
                    kw = json.loads(obj.keywords or "[]")
                    if not _menciona(texto, kw):
                        continue
                    if link and db.query(Contenido).filter(Contenido.url == link).first():
                        continue
                    item = Contenido(
                        fuente_tipo=  "rss",
                        fuente_nombre=nombre,
                        url=link, titulo=titulo, texto=resumen,
                        autor=autor, fecha_pub=pub,
                        objetivo_id=obj.id,
                        raw_json=json.dumps({"title": titulo, "summary": resumen}, ensure_ascii=False)
                    )
                    db.add(item)
                    total += 1
                    log.info(f"  + [{obj.nombre}] {titulo[:70]}")
            db.commit()
        except Exception as e:
            log.error(f"Error {nombre}: {e}")
            db.rollback()

    log.info(f"RSS: {total} artículos nuevos.")
    return total
