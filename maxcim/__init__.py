"""MAXCIM application factory."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from flask import Flask, jsonify, redirect, request, url_for
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge, TooManyRequests

from .config import Config
from .demo import seed_demo_data
from .extensions import csrf, db, limiter, login_manager


def create_app(config: dict | type[Config] | None = None) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "static"),
    )
    app.config.from_object(Config)
    if config:
        if isinstance(config, dict):
            app.config.update(config)
            if config.get("SECRET_KEY"):
                app.config["SECRET_KEY_EPHEMERAL"] = False
        else:
            app.config.from_object(config)

    if app.config["AUTH_PROVIDER"] not in {"demo", "cima", "google"}:
        raise RuntimeError("AUTH_PROVIDER debe ser 'demo', 'cima' o 'google'.")
    if app.config["AUTH_PROVIDER"] != "demo":
        # An institutional identity provider must never activate fixture accounts
        # merely because an old environment still contains SEED_DEMO_DATA=true.
        app.config["SEED_DEMO_DATA"] = False
    if app.config["AUTH_PROVIDER"] == "cima":
        encryption_key = str(app.config.get("CIMA_TOKEN_ENCRYPTION_KEY") or "").strip()
        if not encryption_key:
            raise RuntimeError("CIMA_TOKEN_ENCRYPTION_KEY es obligatoria con AUTH_PROVIDER=cima.")
        try:
            Fernet(encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise RuntimeError("CIMA_TOKEN_ENCRYPTION_KEY debe ser una clave Fernet válida.") from exc
        if app.config.get("SECRET_KEY_EPHEMERAL") and not app.config.get("TESTING"):
            raise RuntimeError("SECRET_KEY debe ser persistente con AUTH_PROVIDER=cima.")
        if not app.config.get("TESTING"):
            if len(str(app.config.get("SECRET_KEY") or "")) < 32:
                raise RuntimeError("SECRET_KEY debe contener al menos 32 caracteres.")
            if urlsplit(app.config["CIMA_API_BASE_URL"]).scheme != "https":
                raise RuntimeError("CIMA_API_BASE_URL debe usar HTTPS.")
            if not app.config.get("CIMA_API_VERIFY_TLS"):
                raise RuntimeError("CIMA_API_VERIFY_TLS debe permanecer activo.")
            if not app.config.get("SESSION_COOKIE_SECURE") and not app.config.get(
                "CIMA_ALLOW_INSECURE_LOCAL_COOKIES"
            ):
                raise RuntimeError(
                    "SESSION_COOKIE_SECURE debe estar activo con AUTH_PROVIDER=cima. "
                    "Para una prueba HTTP local, habilita explícitamente "
                    "CIMA_ALLOW_INSECURE_LOCAL_COOKIES."
                )
            if not str(app.config.get("CIMA_API_TEACHER_ID_CLAIM") or "").strip():
                raise RuntimeError(
                    "CIMA_API_TEACHER_ID_CLAIM debe ser confirmado y configurado "
                    "antes del uso institucional."
                )
        if app.config["CIMA_API_SYSTEM_ID"] <= 0:
            raise RuntimeError("CIMA_API_SYSTEM_ID debe ser mayor que cero.")
        if app.config["CIMA_API_TIMEOUT_SECONDS"] <= 0:
            raise RuntimeError("CIMA_API_TIMEOUT_SECONDS debe ser mayor que cero.")
        if app.config["CIMA_API_SESSION_MAX_AGE_SECONDS"] < 300:
            raise RuntimeError("CIMA_API_SESSION_MAX_AGE_SECONDS debe ser al menos 300.")

    if app.config["AUTH_PROVIDER"] == "google":
        client_id = str(app.config.get("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
        client_secret = str(app.config.get("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
        redirect_uri = str(app.config.get("GOOGLE_OAUTH_REDIRECT_URI") or "").strip()
        workspace_domain = str(app.config.get("GOOGLE_WORKSPACE_DOMAIN") or "").strip().casefold()
        allowed_emails = tuple(app.config.get("GOOGLE_ALLOWED_TEACHER_EMAILS") or ())
        flow_max_age = int(app.config.get("GOOGLE_OAUTH_FLOW_MAX_AGE_SECONDS") or 0)
        oauth_timeout = float(app.config.get("GOOGLE_OAUTH_TIMEOUT_SECONDS") or 0)

        if not client_id or not client_secret:
            raise RuntimeError(
                "GOOGLE_OAUTH_CLIENT_ID y GOOGLE_OAUTH_CLIENT_SECRET son obligatorios."
            )
        if not redirect_uri:
            raise RuntimeError("GOOGLE_OAUTH_REDIRECT_URI es obligatoria.")
        redirect_parts = urlsplit(redirect_uri)
        if (
            redirect_parts.scheme not in {"http", "https"}
            or not redirect_parts.netloc
            or redirect_parts.query
            or redirect_parts.fragment
        ):
            raise RuntimeError("GOOGLE_OAUTH_REDIRECT_URI debe ser una URL absoluta sin parámetros.")
        local_redirect = (
            redirect_parts.scheme == "http"
            and redirect_parts.hostname in {"127.0.0.1", "localhost"}
        )
        if redirect_parts.scheme != "https" and not local_redirect:
            raise RuntimeError(
                "GOOGLE_OAUTH_REDIRECT_URI debe usar HTTPS, salvo en localhost."
            )
        if not workspace_domain or "/" in workspace_domain or "@" in workspace_domain:
            raise RuntimeError("GOOGLE_WORKSPACE_DOMAIN no es válido.")
        if not allowed_emails:
            raise RuntimeError(
                "GOOGLE_ALLOWED_TEACHER_EMAILS debe incluir al menos un docente."
            )
        if any(
            not str(email).strip().casefold().endswith(f"@{workspace_domain}")
            for email in allowed_emails
        ):
            raise RuntimeError(
                "Todos los correos autorizados deben pertenecer a GOOGLE_WORKSPACE_DOMAIN."
            )
        if not 60 <= flow_max_age <= 900:
            raise RuntimeError("GOOGLE_OAUTH_FLOW_MAX_AGE_SECONDS debe estar entre 60 y 900.")
        if not 1 <= oauth_timeout <= 30:
            raise RuntimeError("GOOGLE_OAUTH_TIMEOUT_SECONDS debe estar entre 1 y 30.")
        if app.config.get("SECRET_KEY_EPHEMERAL") and not app.config.get("TESTING"):
            raise RuntimeError("SECRET_KEY debe ser persistente con AUTH_PROVIDER=google.")
        if not app.config.get("TESTING"):
            if len(str(app.config.get("SECRET_KEY") or "")) < 32:
                raise RuntimeError("SECRET_KEY debe contener al menos 32 caracteres.")
            insecure_local = local_redirect and app.config.get(
                "GOOGLE_ALLOW_INSECURE_LOCAL_COOKIES"
            )
            if not app.config.get("SESSION_COOKIE_SECURE") and not insecure_local:
                raise RuntimeError(
                    "SESSION_COOKIE_SECURE debe estar activo con AUTH_PROVIDER=google. "
                    "Para localhost HTTP, habilita explícitamente "
                    "GOOGLE_ALLOW_INSECURE_LOCAL_COOKIES."
                )

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    from .models import (  # noqa: F401
        CimaIdentity,
        CimaLearningSession,
        CimaSession,
        GoogleIdentity,
        User,
    )
    from .routes.api import api_bp
    from .routes.auth import auth_bp
    from .routes.web import web_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id)) if user_id.isdigit() else None

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/") or request.path.startswith("/media/"):
            return jsonify({"error": "Debes iniciar sesión."}), 401
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error: CSRFError):
        if request.path.startswith("/api/"):
            return jsonify({"error": "La sesión de seguridad expiró. Recarga la página."}), 400
        return error.description, 400

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_error):
        return jsonify({"error": "El archivo supera el límite permitido de 16 MB."}), 413

    @app.errorhandler(TooManyRequests)
    def handle_rate_limit(_error):
        return jsonify({"error": "Demasiadas solicitudes. Espera un momento e inténtalo otra vez."}), 429

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error: SQLAlchemyError):
        db.session.rollback()
        app.logger.exception("Database operation failed", exc_info=error)
        if request.path.startswith("/api/"):
            return jsonify({"error": "No se pudo completar la operación en la base de datos."}), 500
        return "No se pudo cargar la información.", 500

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; media-src 'self' blob:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        if request.is_secure or app.config["SESSION_COOKIE_SECURE"]:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.path.startswith(
            ("/login", "/dashboard", "/aulas/", "/material", "/sesiones", "/api/", "/media/")
        ):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    if app.config.get("AUTO_CREATE_DB", True):
        with app.app_context():
            db.create_all()
            if app.config.get("SEED_DEMO_DATA", True):
                seed_demo_data(app)

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Create the safe, fictional demonstration dataset."""
        seed_demo_data(app, force=True)
        print("MAXCIM demo data ready.")

    return app


__all__ = ["create_app"]
