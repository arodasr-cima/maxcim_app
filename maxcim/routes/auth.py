"""Session authentication for demo and official CIMA accounts."""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import (
    Blueprint,
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

from ..extensions import limiter
from ..models import User
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

auth_bp = Blueprint("auth", __name__)


def _safe_next_url(target: str) -> bool:
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc and target.startswith("/")


def _is_cima_provider() -> bool:
    return current_app.config["AUTH_PROVIDER"] == "cima"


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
        else:
            email = identity_value.lower()
            candidate = User.query.filter_by(email=email).first()
            if candidate and candidate.check_password(password):
                user = candidate
            else:
                flash("Correo o contraseña incorrectos.", "error")

        if user is not None:
            login_user(user)
            target = request.args.get("next", "")
            return redirect(target if _safe_next_url(target) else url_for("web.dashboard"))

    return render_template(
        "login.html",
        auth_provider=current_app.config["AUTH_PROVIDER"],
        demo_mode=current_app.config["DEMO_MODE"],
        demo_email=current_app.config["DEMO_EMAIL"],
        demo_password=current_app.config["DEMO_PASSWORD"],
    )


@auth_bp.post("/logout")
def logout():
    session_id = session.pop("cima_session_id", None)
    if _is_cima_provider():
        revoke_cima_session(session_id)
    logout_user()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("auth.login"))
