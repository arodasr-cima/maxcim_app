"""Encrypted, server-side lifecycle for CIMA access tokens."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import CimaIdentity, CimaSession, User
from .cima_api import AuthenticatedTeacher, CimaAuthenticationError, CimaConfigurationError


class CimaSessionExpired(CimaAuthenticationError):
    def __init__(self):
        super().__init__("La sesión institucional venció. Inicia sesión nuevamente.")


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _cipher(config: dict[str, Any]) -> Fernet:
    raw_key = str(config.get("CIMA_TOKEN_ENCRYPTION_KEY") or "").strip()
    if not raw_key:
        raise CimaConfigurationError("Falta CIMA_TOKEN_ENCRYPTION_KEY.")
    try:
        return Fernet(raw_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise CimaConfigurationError("CIMA_TOKEN_ENCRYPTION_KEY no es una clave Fernet válida.") from exc


def _synthetic_email(teacher_id: str) -> str:
    digest = hashlib.sha256(teacher_id.encode("utf-8")).hexdigest()[:24]
    return f"cima-{digest}@maxcim.invalid"


def _initials(display_name: str) -> str:
    parts = [part for part in display_name.split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "DC"


def _expiry(authenticated: AuthenticatedTeacher, max_age_seconds: int) -> datetime:
    now = utcnow()
    if max_age_seconds < 300:
        raise CimaConfigurationError("La duración máxima de sesión CIMA debe ser al menos 300 segundos.")
    maximum = now + timedelta(seconds=max_age_seconds)
    if authenticated.expires_at is None:
        return maximum
    upstream = authenticated.expires_at.astimezone(UTC).replace(tzinfo=None)
    if upstream <= now:
        raise CimaSessionExpired()
    return min(upstream, maximum)


def establish_cima_session(
    config: dict[str, Any], authenticated: AuthenticatedTeacher
) -> tuple[User, str]:
    """Upsert the institutional identity and persist only an encrypted JWT."""

    expires_at = _expiry(
        authenticated,
        int(config.get("CIMA_API_SESSION_MAX_AGE_SECONDS", 28_800)),
    )
    encrypted = _cipher(config).encrypt(authenticated.authorization.encode("utf-8")).decode("ascii")

    for attempt in range(2):
        try:
            identity = CimaIdentity.query.filter_by(teacher_id=authenticated.teacher_id).first()
            if identity is None:
                email = _synthetic_email(authenticated.teacher_id)
                user = User.query.filter_by(email=email).first()
                if user is None:
                    display_name = authenticated.display_name or "Docente CIMA"
                    user = User(
                        email=email,
                        display_name=display_name,
                        initials=_initials(display_name),
                        role="DOCENTE",
                    )
                    user.set_password(secrets.token_urlsafe(48))
                    db.session.add(user)
                    db.session.flush()
                identity = CimaIdentity(teacher_id=authenticated.teacher_id, user_id=user.id)
                db.session.add(identity)
                db.session.flush()
            else:
                user = identity.user
                if authenticated.display_name and user.display_name != authenticated.display_name:
                    user.display_name = authenticated.display_name
                    user.initials = _initials(authenticated.display_name)

            CimaSession.query.filter(CimaSession.expires_at <= utcnow()).delete(
                synchronize_session=False
            )
            session_id = secrets.token_urlsafe(32)
            db.session.add(
                CimaSession(
                    id=session_id,
                    identity_id=identity.id,
                    user_id=user.id,
                    token_ciphertext=encrypted,
                    expires_at=expires_at,
                )
            )
            db.session.commit()
            return user, session_id
        except IntegrityError:
            db.session.rollback()
            if attempt:
                raise

    raise RuntimeError("No se pudo crear la sesión CIMA.")


def load_cima_access(config: dict[str, Any], session_id: str, user_id: int) -> tuple[str, str]:
    record = db.session.get(CimaSession, str(session_id or ""))
    if record is None or record.user_id != user_id:
        raise CimaSessionExpired()
    if record.expires_at <= utcnow():
        db.session.delete(record)
        db.session.commit()
        raise CimaSessionExpired()
    try:
        authorization = _cipher(config).decrypt(record.token_ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError):
        db.session.delete(record)
        db.session.commit()
        raise CimaSessionExpired() from None
    return authorization, record.identity.teacher_id


def revoke_cima_session(session_id: str | None) -> None:
    if not session_id:
        return
    record = db.session.get(CimaSession, session_id)
    if record is not None:
        db.session.delete(record)
        db.session.commit()
