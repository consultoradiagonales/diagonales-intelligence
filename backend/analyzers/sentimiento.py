"""
Motor de análisis de sentimiento en español.
Modelo: pysentimiento (entrenado en Twitter latinoamericano).
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..db.models import Contenido, Comentario, Sentimiento, SentimientoComentario, ResumenDiario

log = logging.getLogger(__name__)
_analyzer = None


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        log.info("Cargando modelo de sentimiento (primera vez puede demorar ~30s)...")
        from pysentimiento import create_analyzer
        _analyzer = create_analyzer(task="sentiment", lang="es")
        log.info("Modelo listo.")
    return _analyzer


def _analizar(texto: str) -> dict | None:
    if not texto or len(texto.strip()) < 5:
        return None
    try:
        r = _get_analyzer().predict(texto[:1000])
        return {
            "sentimiento": r.output,
            "score_pos": r.probas.get("POS", 0),
            "score_neg": r.probas.get("NEG", 0),
            "score_neu": r.probas.get("NEU", 0),
        }
    except Exception as e:
        log.debug(f"Error sentimiento: {e}")
        return None


def analizar_pendiente(db: Session, batch: int = 200) -> int:
    ahora = datetime.now(timezone.utc)

    # Contenido sin analizar
    pendientes = (
        db.query(Contenido)
        .outerjoin(Sentimiento, Sentimiento.contenido_id == Contenido.id)
        .filter(Sentimiento.id == None, Contenido.objetivo_id != None)
        .limit(batch).all()
    )

    ok = 0
    for item in pendientes:
        texto = f"{item.titulo or ''} {item.texto or ''}".strip()
        r = _analizar(texto)
        if r:
            db.add(Sentimiento(
                contenido_id=item.id, objetivo_id=item.objetivo_id,
                fecha_analisis=ahora, sentimiento=r["sentimiento"],
                score_pos=r["score_pos"], score_neg=r["score_neg"], score_neu=r["score_neu"]
            ))
            ok += 1

    db.commit()

    # Comentarios sin analizar
    pendientes_com = (
        db.query(Comentario)
        .outerjoin(SentimientoComentario, SentimientoComentario.comentario_id == Comentario.id)
        .filter(SentimientoComentario.id == None, Comentario.objetivo_id != None)
        .limit(batch).all()
    )

    ok_c = 0
    for com in pendientes_com:
        r = _analizar(com.texto)
        if r:
            db.add(SentimientoComentario(
                comentario_id=com.id, objetivo_id=com.objetivo_id,
                fecha_analisis=ahora, sentimiento=r["sentimiento"],
                score_pos=r["score_pos"], score_neg=r["score_neg"], score_neu=r["score_neu"]
            ))
            ok_c += 1

    db.commit()
    log.info(f"Sentimiento: {ok} contenidos, {ok_c} comentarios analizados.")
    return ok + ok_c


def calcular_resumen_diario(db: Session, fecha: str = None) -> None:
    if not fecha:
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    from sqlalchemy import func, case
    from ..db.models import Objetivo, Engagement

    objetivos = db.query(Objetivo).filter(Objetivo.activo == True).all()

    for obj in objetivos:
        conteos = (
            db.query(Sentimiento.sentimiento, func.count().label("cnt"))
            .join(Contenido, Contenido.id == Sentimiento.contenido_id)
            .filter(Contenido.objetivo_id == obj.id)
            .filter(func.strftime("%Y-%m-%d", Sentimiento.fecha_analisis) == fecha)
            .group_by(Sentimiento.sentimiento)
            .all()
        )
        d = {r.sentimiento: r.cnt for r in conteos}
        total = sum(d.values()) or 1

        eng_total = (
            db.query(func.sum(
                Engagement.likes + Engagement.comentarios + Engagement.vistas
            ))
            .join(Contenido, Contenido.id == Engagement.contenido_id)
            .filter(Contenido.objetivo_id == obj.id)
            .filter(func.strftime("%Y-%m-%d", Contenido.fecha_scrape) == fecha)
            .scalar() or 0
        )

        from sqlalchemy.dialects import sqlite
        import json

        fuentes_rows = (
            db.query(Contenido.fuente_nombre, func.count().label("cnt"))
            .filter(Contenido.objetivo_id == obj.id)
            .filter(func.strftime("%Y-%m-%d", Contenido.fecha_scrape) == fecha)
            .group_by(Contenido.fuente_nombre)
            .order_by(func.count().desc())
            .all()
        )
        fuentes = {r.fuente_nombre: r.cnt for r in fuentes_rows}

        existing = (
            db.query(ResumenDiario)
            .filter(ResumenDiario.objetivo_id == obj.id, ResumenDiario.fecha == fecha)
            .first()
        )
        datos = dict(
            total_menciones=total,
            pct_positivo=round(d.get("POS", 0) / total * 100, 1),
            pct_negativo=round(d.get("NEG", 0) / total * 100, 1),
            pct_neutro=round(d.get("NEU", 0) / total * 100, 1),
            total_engagement=int(eng_total),
            fuentes_json=json.dumps(fuentes, ensure_ascii=False)
        )
        if existing:
            for k, v in datos.items():
                setattr(existing, k, v)
        else:
            db.add(ResumenDiario(objetivo_id=obj.id, fecha=fecha, **datos))

        log.info(f"Resumen [{obj.nombre}] {fecha}: "
                 f"{total} mencs | POS:{datos['pct_positivo']}% NEG:{datos['pct_negativo']}%")

    db.commit()
