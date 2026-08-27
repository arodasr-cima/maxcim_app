from __future__ import annotations

from datetime import UTC, datetime

from ..extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC)


class LearningSession(db.Model):
    __tablename__ = "learning_sessions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    classroom = db.Column(db.String(100), nullable=False)
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="programada")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner = db.relationship("User", back_populates="sessions")
