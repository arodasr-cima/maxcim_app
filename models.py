from __future__ import annotations

from extensions import db


class Material(db.Model):
    """Material prepared by a teacher for an activity with MAXCIM."""

    __tablename__ = "material"

    id = db.Column(db.Integer, primary_key=True)
    nombre_material = db.Column(db.String(255), nullable=False)
    path_audio = db.Column(db.String(500), nullable=False)
    path_texto = db.Column(db.String(500), nullable=False)
    path_audio_resumen = db.Column(db.String(500), nullable=False)
    path_texto_resumen = db.Column(db.String(500), nullable=False)
    path_preguntas = db.Column(db.String(500), nullable=False)
    fecha_subido = db.Column(db.Date, server_default=db.func.current_date())
    # Institutional ID returned by the school's API. It is deliberately not a
    # local FK: the institutional database remains the source of truth.
    fk_user = db.Column(db.String(50), nullable=True, index=True)

    preguntas = db.relationship(
        "Pregunta",
        back_populates="material",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Pregunta(db.Model):
    """Teacher-reviewable question generated from a material."""

    __tablename__ = "pregunta"

    id = db.Column(db.Integer, primary_key=True)
    id_material = db.Column(
        db.Integer,
        db.ForeignKey("material.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo = db.Column(db.String(30), nullable=False)
    enunciado = db.Column(db.Text, nullable=False)
    respuesta_esperada = db.Column(db.Text, nullable=True)
    orden = db.Column(db.Integer, nullable=False, default=0)
    generada_por_ia = db.Column(db.Boolean, nullable=False, default=True)
    editada_por_docente = db.Column(db.Boolean, nullable=False, default=False)
    estado = db.Column(db.String(30), nullable=False, default="pendiente_revision", index=True)
    aprobada_por = db.Column(db.String(50), nullable=True)
    aprobada_en = db.Column(db.DateTime, nullable=True)
    creada_en = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    material = db.relationship("Material", back_populates="preguntas")


class SesionInteraccion(db.Model):
    """One oral interaction between MAXCIM and one identified student."""

    __tablename__ = "sesion_interaccion"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), nullable=False, unique=True, index=True)
    id_docente_institucional = db.Column(db.String(50), nullable=False, index=True)
    id_alumno_institucional = db.Column(db.String(50), nullable=True, index=True)
    id_aula_institucional = db.Column(db.String(50), nullable=False, index=True)
    id_material = db.Column(
        db.Integer,
        db.ForeignKey("material.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    objetivo = db.Column(db.Text, nullable=True)
    estado = db.Column(
        db.String(30),
        nullable=False,
        default="esperando_identificacion",
        index=True,
    )
    alumno_nombre = db.Column(db.String(255), nullable=True)
    confianza_reconocimiento = db.Column(db.Numeric(5, 4), nullable=True)
    creada_en = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    iniciada_en = db.Column(db.DateTime, nullable=True)
    finalizada_en = db.Column(db.DateTime, nullable=True)
    revisada_por_docente = db.Column(db.Boolean, nullable=False, default=False)
    observaciones_docente = db.Column(db.Text, nullable=True)

    material = db.relationship("Material")
    turnos = db.relationship(
        "TurnoConversacion",
        back_populates="sesion",
        cascade="all, delete-orphan",
        order_by="TurnoConversacion.orden",
        lazy="selectin",
    )
    evaluacion = db.relationship(
        "EvaluacionInteraccion",
        back_populates="sesion",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )


class TurnoConversacion(db.Model):
    """A transcript turn; no facial embedding or image is stored here."""

    __tablename__ = "turno_conversacion"
    __table_args__ = (
        db.UniqueConstraint("id_sesion", "orden", name="uq_turno_orden"),
    )

    id = db.Column(db.Integer, primary_key=True)
    id_sesion = db.Column(
        db.Integer,
        db.ForeignKey("sesion_interaccion.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_pregunta = db.Column(
        db.Integer,
        db.ForeignKey("pregunta.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    orden = db.Column(db.Integer, nullable=False)
    emisor = db.Column(db.String(20), nullable=False)
    texto_transcrito = db.Column(db.Text, nullable=False)
    path_audio = db.Column(db.String(500), nullable=True)
    tiempo_respuesta_ms = db.Column(db.Integer, nullable=True)
    respuesta_correcta = db.Column(db.Boolean, nullable=True)
    necesito_ayuda = db.Column(db.Boolean, nullable=False, default=False)
    creada_en = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    sesion = db.relationship("SesionInteraccion", back_populates="turnos")
    pregunta = db.relationship("Pregunta")


class EvaluacionInteraccion(db.Model):
    """AI-assisted evaluation that must be reviewed by a teacher."""

    __tablename__ = "evaluacion_interaccion"

    id = db.Column(db.Integer, primary_key=True)
    id_sesion = db.Column(
        db.Integer,
        db.ForeignKey("sesion_interaccion.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    preguntas_realizadas = db.Column(db.Integer, nullable=False, default=0)
    respuestas_registradas = db.Column(db.Integer, nullable=False, default=0)
    respuestas_correctas = db.Column(db.Integer, nullable=False, default=0)
    promedio_respuesta_ms = db.Column(db.Integer, nullable=True)
    porcentaje_participacion = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    porcentaje_comprension = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    porcentaje_interaccion_oral = db.Column(db.Numeric(5, 2), nullable=True)
    porcentaje_general = db.Column(db.Numeric(5, 2), nullable=True)
    criterios_json = db.Column(db.Text, nullable=True)
    resumen_ia = db.Column(db.Text, nullable=True)
    estado = db.Column(db.String(30), nullable=False, default="pendiente_revision", index=True)
    retroalimentacion_docente = db.Column(db.Text, nullable=True)
    revisada_por = db.Column(db.String(50), nullable=True)
    revisada_en = db.Column(db.DateTime, nullable=True)
    creada_en = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    actualizada_en = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    sesion = db.relationship("SesionInteraccion", back_populates="evaluacion")


class EventoReconocimiento(db.Model):
    """Auditable recognition result without storing biometric templates."""

    __tablename__ = "evento_reconocimiento"

    id = db.Column(db.Integer, primary_key=True)
    id_sesion = db.Column(
        db.Integer,
        db.ForeignKey("sesion_interaccion.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    id_persona_institucional = db.Column(db.String(50), nullable=False, index=True)
    tipo_persona = db.Column(db.String(30), nullable=False)
    nombre_persona = db.Column(db.String(255), nullable=True)
    confianza = db.Column(db.Numeric(5, 4), nullable=False)
    estado = db.Column(db.String(30), nullable=False)
    motivo = db.Column(db.String(255), nullable=True)
    recibida_en = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    sesion = db.relationship("SesionInteraccion")
