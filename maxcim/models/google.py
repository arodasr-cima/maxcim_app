"""Stable Google Workspace identities linked to local MAXCIM users."""

from __future__ import annotations

from datetime import UTC, datetime

from ..extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class GoogleIdentity(db.Model):
    __tablename__ = "google_identities"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")
