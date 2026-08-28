"""Server-side identity and encrypted access-token records for CIMA."""

from __future__ import annotations

from datetime import UTC, datetime

from ..extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class CimaIdentity(db.Model):
    __tablename__ = "cima_identities"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.String(120), unique=True, nullable=False, index=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")


class CimaSession(db.Model):
    __tablename__ = "cima_sessions"

    id = db.Column(db.String(64), primary_key=True)
    identity_id = db.Column(
        db.Integer,
        db.ForeignKey("cima_identities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_ciphertext = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    identity = db.relationship("CimaIdentity")
    user = db.relationship("User")


class CimaLearningSession(db.Model):
    """Institutional classroom identity for a locally planned session."""

    __tablename__ = "cima_learning_sessions"

    id = db.Column(db.Integer, primary_key=True)
    learning_session_id = db.Column(
        db.Integer,
        db.ForeignKey("learning_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    classroom_id = db.Column(db.String(120), nullable=False)
    classroom_type = db.Column(db.String(1), nullable=False)

    learning_session = db.relationship("LearningSession")
