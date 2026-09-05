from __future__ import annotations

from datetime import UTC, date, datetime

from extensions import db


def _utc_now() -> datetime:
    """UTC stored without tzinfo for compatibility with MySQL DATETIME.

    Mirrors app.utc_now() — kept local to avoid a models -> app import.
    """
    return datetime.now(UTC).replace(tzinfo=None)


# Valores permitidos de `material.tipo_material` (ver bd_app.sql). Un cuento
# usa todas las rutas; una oración solo guarda su texto en `path_preguntas`.
TIPO_CUENTO = "cuento"
TIPO_ORACION = "oracion"
TIPOS_MATERIAL = (TIPO_CUENTO, TIPO_ORACION)


class Periodo(db.Model):
    """Bimestre académico definido para un año escolar.

    Refleja exactamente `periodo` en bd_app.sql; ese archivo es la fuente de
    verdad para columnas, tipos e índices.
    """

    __tablename__ = "periodo"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)

    materiales = db.relationship("Material", back_populates="periodo")
    interacciones = db.relationship("Interaccion", back_populates="periodo")


class Material(db.Model):
    """Material prepared by a teacher for an activity with MAXCIM.

    Mirrors `material` in bd_app.sql exactly — see that file for the source
    of truth on columns, types and indexes.
    """

    __tablename__ = "material"

    id = db.Column(db.Integer, primary_key=True)
    nombre_material = db.Column(db.String(255), nullable=False)
    tipo_material = db.Column(db.String(255), nullable=False)
    path_audio = db.Column(db.String(500), nullable=True)
    path_texto = db.Column(db.String(500), nullable=True)
    path_audio_resumen = db.Column(db.String(500), nullable=True)
    path_texto_resumen = db.Column(db.String(500), nullable=True)
    # Ruta del JSON de preguntas en un cuento; texto de las oraciones en una
    # oración. Es TEXT porque las oraciones no caben en VARCHAR(500).
    path_preguntas = db.Column(db.Text, nullable=False)
    # Application-side default. SQLAlchemy would render func.current_date()
    # as DEFAULT CURRENT_DATE for MySQL, which some managed MySQL versions
    # reject during schema creation.
    fecha_subido = db.Column(db.Date, nullable=False, default=date.today)
    # ID institucional de la docente (`idPersona` de CIMA, p.ej. "70385"). No es
    # una FK real: la tabla `docente` vive en la API institucional, no en esta
    # base (ver bd_app.sql).
    fk_user = db.Column(db.String(50), nullable=False, index=True)
    # Nombre de la docente (ya normalizado, p.ej. "Rodas Rosales Oscar Alexis")
    # tal como estaba en su sesión al crear el material. Copia para que la API
    # del robot pueda listar materiales por nombre (`?docente=`) y mostrarlo sin
    # volver a consultar a CIMA. Nulo en registros creados antes de la columna.
    fk_user_name = db.Column(db.String(255), nullable=True)
    # Bimestre académico del material; nulo si queda fuera de todos los periodos definidos.
    id_periodo = db.Column(
        db.Integer,
        db.ForeignKey("periodo.id"),
        nullable=True,
        index=True,
    )

    interacciones = db.relationship(
        "Interaccion",
        back_populates="material",
        lazy="selectin",
    )
    periodo = db.relationship("Periodo", back_populates="materiales")

    @property
    def es_oracion(self) -> bool:
        return self.tipo_material == TIPO_ORACION

    @property
    def es_cuento(self) -> bool:
        return self.tipo_material == TIPO_CUENTO


class Interaccion(db.Model):
    """One question/answer turn between an identified student and MAXCIM.
    Mirrors `interaccion` in bd_app.sql exactly.

    Usually the turn is about a `material` the teacher prepared. When
    `id_material` is NULL the turn is a free conversation the student held
    with MAXCIM, not tied to any material; the teacher views label it
    "Conversación".
    """

    __tablename__ = "interaccion"

    id = db.Column(db.Integer, primary_key=True)
    id_material = db.Column(
        db.Integer,
        db.ForeignKey("material.id"),
        nullable=True,
        index=True,
    )
    # ID institucional del alumno, igual que `fk_user` en Material: no es una
    # FK real porque `alumno` también vive en la API institucional.
    fk_alumno = db.Column(db.String(50), nullable=False, index=True)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=_utc_now)
    pregunta = db.Column(db.Text, nullable=False)
    respuesta = db.Column(db.Text, nullable=False)
    path_audio_rpta = db.Column(db.String(500), nullable=False)
    apreciacion_robot = db.Column(db.Text, nullable=False)
    rpta_correcta = db.Column(db.Boolean, nullable=False)
    # Bimestre académico de la interacción; nulo si queda fuera de todos los periodos definidos.
    id_periodo = db.Column(
        db.Integer,
        db.ForeignKey("periodo.id"),
        nullable=True,
        index=True,
    )

    material = db.relationship("Material", back_populates="interacciones")
    periodo = db.relationship("Periodo", back_populates="interacciones")
