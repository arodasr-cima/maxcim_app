"""Session authentication for the demonstrator account."""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from ..extensions import limiter
from ..models import User

auth_bp = Blueprint("auth", __name__)


def _safe_next_url(target: str) -> bool:
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc and target.startswith("/")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            target = request.args.get("next", "")
            return redirect(target if _safe_next_url(target) else url_for("web.dashboard"))
        flash("Correo o contraseña incorrectos.", "error")

    return render_template(
        "login.html",
        demo_mode=current_app.config["DEMO_MODE"],
        demo_email=current_app.config["DEMO_EMAIL"],
        demo_password=current_app.config["DEMO_PASSWORD"],
    )


@auth_bp.post("/logout")
def logout():
    logout_user()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("auth.login"))
