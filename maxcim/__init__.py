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

    if app.config["AUTH_PROVIDER"] not in {"demo", "cima"}:
        raise RuntimeError("AUTH_PROVIDER debe ser 'demo' o 'cima'.")
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

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    from .models import CimaIdentity, CimaLearningSession, CimaSession, User  # noqa: F401
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
