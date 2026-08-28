"""Verification and local linking for institutional Google identities."""

from __future__ import annotations

import secrets
from typing import Any

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import GoogleIdentity, User
from ..models.google import utcnow


class GoogleIdentityError(RuntimeError):
    """Base class for rejected or conflicting Google identities."""


class GoogleTokenError(GoogleIdentityError):
    """The provider token could not be verified."""


class GoogleIdentityConflict(GoogleIdentityError):
    """A stable Google subject conflicts with an existing account link."""


def verify_google_token(
    token: str,
    client_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Verify signature, audience, issuer and expiry with Google's library."""

    if not token or not client_id or timeout_seconds <= 0:
        raise GoogleTokenError("Falta la configuración segura para validar el token.")

    google_request = GoogleRequest()

    def bounded_request(*args, **kwargs):
        kwargs["timeout"] = timeout_seconds
        return google_request(*args, **kwargs)

    try:
        claims = google_id_token.verify_oauth2_token(
            token,
            bounded_request,
            client_id,
        )
    except (GoogleAuthError, ValueError) as exc:
        raise GoogleTokenError("Google rechazó el token de identidad.") from exc
    if not isinstance(claims, dict):
        raise GoogleTokenError("Google devolvió una identidad inválida.")
    return claims


def validate_teacher_claims(
    claims: dict[str, Any],
    *,
    expected_nonce: str,
    workspace_domain: str,
    allowed_emails: tuple[str, ...] | list[str] | set[str],
) -> dict[str, str]:
    """Apply MAXCIM's institutional and teacher-only authorization policy."""

    subject = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().casefold()
    name = " ".join(str(claims.get("name") or "Docente CIMA").split())[:120]
    hosted_domain = str(claims.get("hd") or "").strip().casefold()
    nonce = str(claims.get("nonce") or "")
    domain = workspace_domain.strip().casefold()
    authorized = {item.strip().casefold() for item in allowed_emails if item.strip()}

    if not subject or len(subject) > 255:
        raise GoogleTokenError("El token no contiene un identificador estable.")
    if claims.get("email_verified") is not True:
        raise GoogleTokenError("Google no confirmó el correo institucional.")
    if not expected_nonce or not secrets.compare_digest(nonce, expected_nonce):
        raise GoogleTokenError("La respuesta de Google no corresponde a esta sesión.")
    if not domain or hosted_domain != domain or not email.endswith(f"@{domain}"):
        raise GoogleTokenError("La cuenta no pertenece al dominio institucional autorizado.")
    if email not in authorized:
        raise GoogleTokenError("La cuenta institucional no está autorizada como docente.")

    return {"subject": subject, "email": email, "name": name or "Docente CIMA"}


def _initials(display_name: str) -> str:
    parts = [part for part in display_name.split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "DC"


def establish_google_identity(identity_data: dict[str, str]) -> User:
    """Link Google's immutable subject and create a passwordless local user."""

    subject = identity_data["subject"]
    email = identity_data["email"]
    display_name = identity_data["name"]

    for attempt in range(2):
        try:
            identity = GoogleIdentity.query.filter_by(subject=subject).first()
            if identity is None:
                user = User.query.filter_by(email=email).first()
                existing_link = (
                    GoogleIdentity.query.filter_by(user_id=user.id).first()
                    if user is not None
                    else None
                )
                if existing_link is not None:
                    raise GoogleIdentityConflict(
                        "El usuario local ya está vinculado a otra identidad de Google."
                    )
                if user is None:
                    user = User(
                        email=email,
                        display_name=display_name,
                        initials=_initials(display_name),
                        role="DOCENTE",
                    )
                    user.set_password(secrets.token_urlsafe(48))
                    db.session.add(user)
                    db.session.flush()
                identity = GoogleIdentity(subject=subject, email=email, user_id=user.id)
                db.session.add(identity)
            else:
                user = identity.user
                owner = User.query.filter_by(email=email).first()
                if owner is not None and owner.id != user.id:
                    raise GoogleIdentityConflict(
                        "El correo institucional pertenece a otro usuario local."
                    )
                identity.email = email
                user.email = email

            user.display_name = display_name
            user.initials = _initials(display_name)
            user.role = "DOCENTE"
            identity.last_login_at = utcnow()
            db.session.commit()
            return user
        except IntegrityError:
            db.session.rollback()
            if attempt:
                raise GoogleIdentityConflict(
                    "No se pudo vincular la identidad institucional."
                ) from None
        except GoogleIdentityConflict:
            db.session.rollback()
            raise

    raise GoogleIdentityConflict("No se pudo vincular la identidad institucional.")
