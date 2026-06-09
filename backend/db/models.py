"""
Modelos SQLAlchemy — base de datos del sistema Diagonales Intelligence.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime,
    Boolean, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─── OBJETIVOS ────────────────────────────────────────────────

class Objetivo(Base):
    """Candidato, empresa o persona a monitorear."""
    __tablename__ = "objetivos"

    id          = Column(String(60), primary_key=True)   # slug: milei_javier
    nombre      = Column(String(200), nullable=False)
    tipo        = Column(String(20), nullable=False)     # candidato|empresa|funcionario
    activo      = Column(Boolean, default=True)
    keywords    = Column(Text)                           # JSON array
    redes_json  = Column(Text)                           # JSON {twitter, instagram, ...}
    creado_en   = Column(DateTime, default=datetime.utcnow)

    contenidos  = relationship("Contenido", back_populates="objetivo_rel", lazy="dynamic")
    resumenes   = relationship("ResumenDiario", back_populates="objetivo_rel", lazy="dynamic")


# ─── CONTENIDO RECOLECTADO ────────────────────────────────────

class Contenido(Base):
    """Artículo, video o post recolectado de cualquier fuente."""
    __tablename__ = "contenido"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    fuente_tipo   = Column(String(30), nullable=False)   # rss|youtube|twitter|bcra
    fuente_nombre = Column(String(100), nullable=False)
    url           = Column(String(500), unique=True)
    titulo        = Column(Text)
    texto         = Column(Text)
    autor         = Column(String(200))
    fecha_pub     = Column(String(50))
    fecha_scrape  = Column(DateTime, default=datetime.utcnow, nullable=False)
    objetivo_id   = Column(String(60), ForeignKey("objetivos.id"))
    raw_json      = Column(Text)

    objetivo_rel  = relationship("Objetivo", back_populates="contenidos")
    sentimiento   = relationship("Sentimiento", back_populates="contenido_rel", uselist=False)
    engagement    = relationship("Engagement", back_populates="contenido_rel", uselist=False)
    comentarios   = relationship("Comentario", back_populates="contenido_rel", lazy="dynamic")

    __table_args__ = (
        Index("ix_contenido_objetivo", "objetivo_id"),
        Index("ix_contenido_fecha", "fecha_scrape"),
    )


class Comentario(Base):
    """Comentario en YouTube, Facebook, etc."""
    __tablename__ = "comentarios"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    contenido_id = Column(Integer, ForeignKey("contenido.id"))
    fuente_tipo  = Column(String(30))
    texto        = Column(Text, nullable=False)
    autor        = Column(String(200))
    fecha_pub    = Column(String(50))
    fecha_scrape = Column(DateTime, default=datetime.utcnow, nullable=False)
    likes        = Column(Integer, default=0)
    objetivo_id  = Column(String(60))

    contenido_rel = relationship("Contenido", back_populates="comentarios")
    sentimiento   = relationship("SentimientoComentario", back_populates="comentario_rel", uselist=False)


# ─── SENTIMIENTO ──────────────────────────────────────────────

class Sentimiento(Base):
    __tablename__ = "sentimiento"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    contenido_id  = Column(Integer, ForeignKey("contenido.id"), unique=True)
    objetivo_id   = Column(String(60))
    fecha_analisis = Column(DateTime, default=datetime.utcnow)
    sentimiento   = Column(String(5))    # POS|NEG|NEU
    score_pos     = Column(Float)
    score_neg     = Column(Float)
    score_neu     = Column(Float)
    modelo        = Column(String(50), default="pysentimiento-es")

    contenido_rel = relationship("Contenido", back_populates="sentimiento")


class SentimientoComentario(Base):
    __tablename__ = "sentimiento_comentarios"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    comentario_id  = Column(Integer, ForeignKey("comentarios.id"), unique=True)
    objetivo_id    = Column(String(60))
    fecha_analisis = Column(DateTime, default=datetime.utcnow)
    sentimiento    = Column(String(5))
    score_pos      = Column(Float)
    score_neg      = Column(Float)
    score_neu      = Column(Float)

    comentario_rel = relationship("Comentario", back_populates="sentimiento")


# ─── ENGAGEMENT ───────────────────────────────────────────────

class Engagement(Base):
    __tablename__ = "engagement"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    contenido_id   = Column(Integer, ForeignKey("contenido.id"), unique=True)
    likes          = Column(Integer, default=0)
    comentarios    = Column(Integer, default=0)
    shares         = Column(Integer, default=0)
    vistas         = Column(Integer, default=0)
    reacciones_json = Column(Text)
    fecha_registro = Column(DateTime, default=datetime.utcnow)

    contenido_rel  = relationship("Contenido", back_populates="engagement")


# ─── RESUMEN DIARIO ───────────────────────────────────────────

class ResumenDiario(Base):
    __tablename__ = "resumen_diario"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    objetivo_id      = Column(String(60), ForeignKey("objetivos.id"))
    fecha            = Column(String(10), nullable=False)    # YYYY-MM-DD
    total_menciones  = Column(Integer, default=0)
    pct_positivo     = Column(Float, default=0)
    pct_negativo     = Column(Float, default=0)
    pct_neutro       = Column(Float, default=0)
    total_engagement = Column(Integer, default=0)
    fuentes_json     = Column(Text)

    objetivo_rel = relationship("Objetivo", back_populates="resumenes")

    __table_args__ = (
        UniqueConstraint("objetivo_id", "fecha", name="uq_resumen_dia"),
    )


# ─── CONSULTAS BCRA/ANSES ─────────────────────────────────────

class ConsultaIdentidad(Base):
    """Registro de consultas BCRA, ANSES, AFIP sobre personas/empresas."""
    __tablename__ = "consultas_identidad"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    objetivo_id   = Column(String(60))
    tipo_consulta = Column(String(30))   # bcra|anses|afip|boletín
    identificador = Column(String(20))   # DNI / CUIT / CUIL
    resultado_json = Column(Text)
    estado        = Column(String(20))   # sin_deudas|con_deudas|error|pendiente
    fuente_url    = Column(String(300))
    fecha_consulta = Column(DateTime, default=datetime.utcnow)
    confianza     = Column(String(10), default="alta")  # alta|media|baja
