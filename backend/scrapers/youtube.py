"""Scraper YouTube Data API v3 — videos y comentarios."""
import json, logging, os
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from ..db.models import Contenido, Comentario, Engagement, Objetivo

log = logging.getLogger(__name__)


def _build(api_key: str):
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=api_key)


def ejecutar(db: Session, dias_atras: int = 1) -> int:
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        log.warning("YOUTUBE_API_KEY no configurada. Agregar en .env")
        return 0

    yt = _build(api_key)
    objetivos = db.query(Objetivo).filter(Objetivo.activo == True).all()
    total = 0
    desde = (datetime.now(timezone.utc) - timedelta(days=dias_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for obj in objetivos:
        kw_list = json.loads(obj.keywords or "[]")
        videos_unicos: dict[str, dict] = {}

        for kw in kw_list:
            try:
                resp = yt.search().list(
                    q=kw, part="snippet", type="video", maxResults=50,
                    publishedAfter=desde, relevanceLanguage="es",
                    regionCode="AR", order="date"
                ).execute()
                for v in resp.get("items", []):
                    vid = v["id"]["videoId"]
                    if vid not in videos_unicos:
                        videos_unicos[vid] = v
            except Exception as e:
                log.error(f"YT search error [{kw}]: {e}")

        if not videos_unicos:
            continue

        # Stats en batch
        ids_batch = list(videos_unicos.keys())[:50]
        stats = {}
        try:
            sr = yt.videos().list(part="statistics", id=",".join(ids_batch)).execute()
            stats = {i["id"]: i.get("statistics", {}) for i in sr.get("items", [])}
        except Exception as e:
            log.error(f"YT stats error: {e}")

        for vid, video in videos_unicos.items():
            snip = video["snippet"]
            url = f"https://www.youtube.com/watch?v={vid}"
            if db.query(Contenido).filter(Contenido.url == url).first():
                continue

            s = stats.get(vid, {})
            item = Contenido(
                fuente_tipo="youtube", fuente_nombre=snip.get("channelTitle", ""),
                url=url, titulo=snip.get("title", ""),
                texto=snip.get("description", ""),
                autor=snip.get("channelTitle", ""),
                fecha_pub=snip.get("publishedAt", ""),
                objetivo_id=obj.id,
                raw_json=json.dumps({"video_id": vid, "stats": s}, ensure_ascii=False)
            )
            db.add(item)
            db.flush()

            eng = Engagement(
                contenido_id=item.id,
                likes=int(s.get("likeCount", 0)),
                comentarios=int(s.get("commentCount", 0)),
                vistas=int(s.get("viewCount", 0))
            )
            db.add(eng)

            # Comentarios
            try:
                cr = yt.commentThreads().list(
                    part="snippet", videoId=vid,
                    maxResults=100, textFormat="plainText", order="relevance"
                ).execute()
                for ct in cr.get("items", []):
                    cs = ct["snippet"]["topLevelComment"]["snippet"]
                    db.add(Comentario(
                        contenido_id=item.id, fuente_tipo="youtube",
                        texto=cs.get("textDisplay", ""),
                        autor=cs.get("authorDisplayName", ""),
                        fecha_pub=cs.get("publishedAt", ""),
                        likes=int(cs.get("likeCount", 0)),
                        objetivo_id=obj.id
                    ))
            except Exception:
                pass

            total += 1
            log.info(f"  + YT [{obj.nombre}] {snip.get('title','')[:60]}")

        db.commit()

    log.info(f"YouTube: {total} videos nuevos.")
    return total
