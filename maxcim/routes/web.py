"""Browser-facing pages and simple form workflows."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..demo import CLASSROOMS, MATERIAL_SKILLS, STAT_CARDS, date_label, local_now, period_label
from ..extensions import db, limiter
from ..models import LearningSession, Material

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def index():
    return redirect(url_for("web.dashboard") if current_user.is_authenticated else url_for("auth.login"))


@web_bp.get("/health")
@limiter.exempt
def health():
    return {"status": "ok", "mode": "demo" if current_app.config["DEMO_MODE"] else "gemini"}


@web_bp.get("/dashboard")
@login_required
def dashboard():
    now = local_now(current_app)
    return render_template(
        "dashboard.html",
        active_nav="tablon",
        user=current_user,
        stat_cards=STAT_CARDS,
        aulas=CLASSROOMS,
        today_label=date_label(now),
        periodo_range=period_label(now),
        demo_mode=current_app.config["DEMO_MODE"],
    )


@web_bp.get("/material")
@login_required
def material():
    materials = (
        Material.query.filter_by(owner_id=current_user.id)
        .order_by(Material.fecha_subido.desc(), Material.id.desc())
        .all()
    )
    return render_template(
        "material.html",
        active_nav="material",
        user=current_user,
        materials=materials,
        skills=MATERIAL_SKILLS,
        demo_mode=current_app.config["DEMO_MODE"],
    )


@web_bp.get("/sesiones")
@login_required
def sesiones():
    sessions = (
        LearningSession.query.filter_by(owner_id=current_user.id)
        .order_by(LearningSession.scheduled_at.desc())
        .all()
    )
    return render_template(
        "sesiones.html",
        active_nav="sesiones",
        user=current_user,
        sessions=sessions,
        classrooms=[item["name"] for item in CLASSROOMS],
        demo_mode=current_app.config["DEMO_MODE"],
    )


@web_bp.post("/sesiones/nueva")
@login_required
@limiter.limit("20 per hour")
def create_session():
    title = (request.form.get("title") or "").strip()
    classroom = (request.form.get("classroom") or "").strip()
    scheduled_raw = (request.form.get("scheduled_at") or "").strip()
    valid_classrooms = {item["name"] for item in CLASSROOMS}
    if not title or len(title) > 120 or classroom not in valid_classrooms:
        flash("Completa correctamente el título y el aula.", "error")
        return redirect(url_for("web.sesiones"))
    try:
        scheduled_at = datetime.fromisoformat(scheduled_raw)
    except ValueError:
        flash("Selecciona una fecha y hora válidas.", "error")
        return redirect(url_for("web.sesiones"))

    db.session.add(
        LearningSession(
            title=title,
            classroom=classroom,
            scheduled_at=scheduled_at,
            status="programada",
            owner_id=current_user.id,
        )
    )
    db.session.commit()
    flash("Sesión programada correctamente.", "success")
    return redirect(url_for("web.sesiones"))


@web_bp.post("/sesiones/<int:session_id>/estado")
@login_required
def toggle_session_status(session_id: int):
    session_item = LearningSession.query.filter_by(id=session_id, owner_id=current_user.id).first_or_404()
    session_item.status = "completada" if session_item.status != "completada" else "programada"
    db.session.commit()
    flash("Estado de la sesión actualizado.", "success")
    return redirect(url_for("web.sesiones"))
