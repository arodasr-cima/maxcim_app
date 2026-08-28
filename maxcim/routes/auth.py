"""Session authentication for demo and official CIMA accounts."""

from __future__ import annotations

import secrets
import time
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_user, logout_user
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2 import OAuth2Error
from requests import RequestException

from ..extensions import limiter
from ..models import GoogleIdentity, User
from ..services.cima_api import (
    CimaAPIError,
    CimaAuthenticationError,
    CimaConfigurationError,
    get_cima_client,
)
from ..services.cima_session import (
    CimaSessionExpired,
    establish_cima_session,
    load_cima_access,
    revoke_cima_session,
)
from ..services.google_identity import (
    GoogleIdentityError,
    establish_google_identity,
    validate_teacher_claims,
    verify_google_token,
)

auth_bp = Blueprint("auth", __name__)
_GOOGLE_OAUTH_EXCHANGE_URL = "https://oauth2.googleapis.com/token"


def _safe_next_url(target: str) -> bool:
    if (
        not target.startswith("/")
        or target.startswith("//")
        or "\\" in target
        or any(ord(character) < 32 or ord(character) == 127 for character in target)
    ):
        return False
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc


def _is_cima_provider() -> bool:
    return current_app.config["AUTH_PROVIDER"] == "cima"


def _is_google_provider() -> bool:
    return current_app.config["AUTH_PROVIDER"] == "google"


def _google_client_config() -> dict:
    redirect_uri = current_app.config["GOOGLE_OAUTH_REDIRECT_URI"]
    return {
        "web": {
            "client_id": current_app.config["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": current_app.config["GOOGLE_OAUTH_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": _GOOGLE_OAUTH_EXCHANGE_URL,
            "redirect_uris": [redirect_uri],
        }
    }


def _build_google_flow(
    *,
    state: str | None = None,
    code_verifier: str | None = None,
    autogenerate_code_verifier: bool = False,
) -> Flow:
    flow = Flow.from_client_config(
        _google_client_config(),
        scopes=["openid", "email", "profile"],
        state=state,
        code_verifier=code_verifier,
        autogenerate_code_verifier=autogenerate_code_verifier,
    )
    flow.redirect_uri = current_app.config["GOOGLE_OAUTH_REDIRECT_URI"]
    return flow


def current_cima_access() -> tuple[str, str]:
    """Return the current authorization header and teacher ID from server storage."""

    cached = getattr(g, "cima_access", None)
    if cached is not None:
        return cached
    session_id = session.get("cima_session_id")
    if not session_id or not current_user.is_authenticated:
        raise CimaSessionExpired()
    access = load_cima_access(current_app.config, session_id, current_user.id)
    g.cima_access = access
    return access


@auth_bp.before_app_request
def enforce_cima_session():
    """A local Flask login is never enough when CIMA is the identity provider."""

    if not _is_cima_provider() or not current_user.is_authenticated:
        return None
    if request.endpoint in {"auth.login", "auth.logout", "web.health", "static"}:
        return None
    try:
        current_cima_access()
    except (CimaSessionExpired, CimaConfigurationError):
        session_id = session.pop("cima_session_id", None)
        revoke_cima_session(session_id)
        logout_user()
        if request.path.startswith("/api/"):
            return jsonify({"error": "La sesión institucional venció."}), 401
        flash("Tu sesión institucional venció. Inicia sesión nuevamente.", "error")
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
    return None


@auth_bp.before_app_request
def enforce_google_session():
    """Reject sessions not established by the active Google provider policy."""

    if not _is_google_provider() or not current_user.is_authenticated:
        return None
    if request.endpoint in {"web.health", "static"}:
        return None

    identity = GoogleIdentity.query.filter_by(user_id=current_user.id).first()
    allowed_emails = {
        str(email).strip().casefold()
        for email in current_app.config["GOOGLE_ALLOWED_TEACHER_EMAILS"]
        if str(email).strip()
    }
    identity_email = str(identity.email if identity is not None else "").strip().casefold()
    session_authorized = (
        session.get("auth_provider") == "google"
        and identity is not None
        and identity_email in allowed_emails
        and current_user.email.strip().casefold() == identity_email
    )
    if session_authorized:
        return None

    logout_user()
    session.clear()
    if request.path.startswith("/api/"):
        return jsonify({"error": "Debes validar tu cuenta institucional de Google."}), 401
    flash("Tu acceso institucional debe validarse nuevamente con Google.", "error")
    if request.endpoint in {
        "auth.login",
        "auth.google_login",
        "auth.google_callback",
        "auth.logout",
    }:
        return None
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    if request.method == "POST":
        identity_value = (request.form.get("identity") or request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        user = None
        if _is_cima_provider():
            try:
                client = get_cima_client(current_app.config)
                identifier = (
                    current_app.config.get("CIMA_API_IDENTIFIER")
                    or request.remote_addr
                    or "MAXCIM-WEB"
                )
                if "@" in identity_value:
                    authenticated = client.authenticate_email(identity_value, password, identifier)
                else:
                    authenticated = client.authenticate_username(identity_value, password, identifier)
                # Validate the configured teacher claim against an authorized
                # endpoint before linking it to private local data.
                client.list_classrooms(authenticated.authorization, authenticated.teacher_id)
                user, session_id = establish_cima_session(current_app.config, authenticated)
                session["cima_session_id"] = session_id
            except CimaAuthenticationError:
                flash("Usuario/correo o contraseña incorrectos.", "error")
            except CimaConfigurationError:
                current_app.logger.error("CIMA authentication configuration is incomplete")
                flash("El acceso institucional necesita configuración del administrador.", "error")
            except CimaAPIError as exc:
                current_app.logger.warning("CIMA authentication failed: %s", type(exc).__name__)
                flash("No se pudo contactar el servicio institucional. Inténtalo nuevamente.", "error")
        elif _is_google_provider():
            flash("Usa el botón de Google para ingresar con tu cuenta institucional.", "error")
        else:
            email = identity_value.lower()
            candidate = User.query.filter_by(email=email).first()
            if candidate and candidate.check_password(password):
                user = candidate
            else:
                flash("Correo o contraseña incorrectos.", "error")

        if user is not None:
            login_user(user)
            session["auth_provider"] = current_app.config["AUTH_PROVIDER"]
            target = request.args.get("next", "")
            return redirect(target if _safe_next_url(target) else url_for("web.dashboard"))

    return render_template(
        "login.html",
        auth_provider=current_app.config["AUTH_PROVIDER"],
        demo_mode=current_app.config["DEMO_MODE"],
        demo_email=current_app.config["DEMO_EMAIL"],
        demo_password=current_app.config["DEMO_PASSWORD"],
        google_workspace_domain=current_app.config["GOOGLE_WORKSPACE_DOMAIN"],
    )


@auth_bp.get("/login/google")
@limiter.limit("20 per minute")
def google_login():
    if not _is_google_provider():
        abort(404)
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    flow = _build_google_flow(autogenerate_code_verifier=True)
    nonce = secrets.token_urlsafe(32)
    authorization_url, state = flow.authorization_url(
        access_type="online",
        include_granted_scopes="true",
        prompt="select_account",
        hd=current_app.config["GOOGLE_WORKSPACE_DOMAIN"],
        nonce=nonce,
    )
    target = request.args.get("next", "")
    session["google_oauth_flow"] = {
        "state": state,
        "nonce": nonce,
        "code_verifier": flow.code_verifier,
        "issued_at": int(time.time()),
        "next": target if _safe_next_url(target) else "",
    }
    return redirect(authorization_url)


@auth_bp.get("/login/google/callback")
@limiter.limit("20 per minute")
def google_callback():
    if not _is_google_provider():
        abort(404)

    oauth_session = session.pop("google_oauth_flow", None)
    supplied_state = request.args.get("state", "")
    expected_state = str((oauth_session or {}).get("state") or "")
    if (
        not oauth_session
        or not supplied_state
        or not expected_state
        or not secrets.compare_digest(supplied_state, expected_state)
    ):
        flash("La respuesta de Google no corresponde a esta sesión. Inténtalo nuevamente.", "error")
        return redirect(url_for("auth.login"))

    age = int(time.time()) - int(oauth_session.get("issued_at") or 0)
    if age < 0 or age > current_app.config["GOOGLE_OAUTH_FLOW_MAX_AGE_SECONDS"]:
        flash("El acceso con Google expiró. Inténtalo nuevamente.", "error")
        return redirect(url_for("auth.login"))
    if request.args.get("error"):
        flash("El acceso con Google fue cancelado o rechazado.", "error")
        return redirect(url_for("auth.login"))

    code = request.args.get("code", "")
    if not code:
        flash("Google no devolvió un código de acceso válido.", "error")
        return redirect(url_for("auth.login"))

    try:
        flow = _build_google_flow(
            state=expected_state,
            code_verifier=str(oauth_session.get("code_verifier") or ""),
        )
        flow.fetch_token(
            code=code,
            timeout=current_app.config["GOOGLE_OAUTH_TIMEOUT_SECONDS"],
        )
        raw_id_token = str(flow.credentials.id_token or "")
        claims = verify_google_token(
            raw_id_token,
            current_app.config["GOOGLE_OAUTH_CLIENT_ID"],
            current_app.config["GOOGLE_OAUTH_TIMEOUT_SECONDS"],
        )
        identity_data = validate_teacher_claims(
            claims,
            expected_nonce=str(oauth_session.get("nonce") or ""),
            workspace_domain=current_app.config["GOOGLE_WORKSPACE_DOMAIN"],
            allowed_emails=current_app.config["GOOGLE_ALLOWED_TEACHER_EMAILS"],
        )
        user = establish_google_identity(identity_data)
    except (GoogleIdentityError, OAuth2Error, RequestException) as exc:
        current_app.logger.warning(
            "Institutional Google login failed: %s", type(exc).__name__
        )
        flash("No se pudo validar tu cuenta institucional de Google.", "error")
        return redirect(url_for("auth.login"))

    target = str(oauth_session.get("next") or "")
    session.clear()
    login_user(user, remember=False, fresh=True)
    session["auth_provider"] = "google"
    session.permanent = True
    return redirect(target if _safe_next_url(target) else url_for("web.dashboard"))


@auth_bp.post("/logout")
def logout():
    session_id = session.pop("cima_session_id", None)
    if _is_cima_provider():
        revoke_cima_session(session_id)
    logout_user()
    session.clear()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("auth.login"))
