from __future__ import annotations

from datetime import UTC, datetime

from ..extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC)


class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    nombre_material = db.Column(db.String(120), nullable=False)
    skill = db.Column(db.String(80), nullable=False, default="Comunicación oral")
    path_audio = db.Column(db.String(255), nullable=False)
    path_texto = db.Column(db.String(255), nullable=False)
    path_audio_resumen = db.Column(db.String(255), nullable=False)
    path_texto_resumen = db.Column(db.String(255), nullable=False)
    path_preguntas = db.Column(db.String(255), nullable=False)
    fecha_subido = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner = db.relationship("User", back_populates="materials")

    @property
    def storage_directory(self) -> str:
        return self.path_texto.split("/", 1)[0]
