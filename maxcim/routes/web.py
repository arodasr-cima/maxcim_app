"""Browser-facing pages and simple form workflows."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from ..demo import CLASSROOMS, MATERIAL_SKILLS, STAT_CARDS, date_label, local_now, period_label
from ..extensions import db, limiter
from ..models import CimaLearningSession, LearningSession, Material
from ..services.cima_api import CimaAPIError, CimaAuthenticationError, Classroom, get_cima_client
from ..services.cima_session import revoke_cima_session
from .auth import current_cima_access

web_bp = Blueprint("web", __name__)


def _official_mode() -> bool:
    return current_app.config["AUTH_PROVIDER"] == "cima"


def _google_mode() -> bool:
    return current_app.config["AUTH_PROVIDER"] == "google"


def _official_classrooms() -> list[Classroom]:
    authorization, teacher_id = current_cima_access()
    return get_cima_client(current_app.config).list_classrooms(authorization, teacher_id)


def _official_login_expired():
    revoke_cima_session(session.pop("cima_session_id", None))
    logout_user()
    flash("La API CIMA rechazó la sesión. Inicia sesión nuevamente.", "error")
    return redirect(url_for("auth.login"))


def _classroom_initials(description: str) -> str:
    parts = [part for part in description.replace("-", " ").split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "AU"


def _classroom_card(classroom: Classroom) -> dict:
    colors = ("#2f61da", "#168a5b", "#b8760a", "#7656c9")
    color_index = sum(ord(char) for char in classroom.institutional_id) % len(colors)
    return {
        "id": classroom.institutional_id,
        "type": classroom.classroom_type,
        "name": classroom.description,
        "grade": classroom.type_label,
        "initials": _classroom_initials(classroom.description),
        "avatar_bg": colors[color_index],
        "status": classroom.status,
    }


def _cima_error_message(error: CimaAPIError) -> str:
    current_app.logger.warning("CIMA data request failed: %s", type(error).__name__)
    if error.status_code == 503:
        return "La API CIMA no está disponible en este momento. Inténtalo nuevamente."
    return "La API CIMA devolvió información con un formato inesperado."


@web_bp.get("/")
def index():
    return redirect(url_for("web.dashboard") if current_user.is_authenticated else url_for("auth.login"))


@web_bp.get("/health")
@limiter.exempt
def health():
    if _official_mode():
        mode = "cima"
    elif _google_mode():
        mode = "google"
    else:
        mode = "demo" if current_app.config["DEMO_MODE"] else "gemini"
    return {"status": "ok", "mode": mode}


@web_bp.get("/dashboard")
@login_required
def dashboard():
    now = local_now(current_app)
    integration_error = None
    classroom_notice = None
    response_status = 200
    if _official_mode():
        try:
            classrooms = _official_classrooms()
        except CimaAuthenticationError:
            return _official_login_expired()
        except CimaAPIError as exc:
            classrooms = []
            integration_error = _cima_error_message(exc)
            response_status = exc.status_code
        aulas = [_classroom_card(item) for item in classrooms]
        regular_count = sum(item.classroom_type == "N" for item in classrooms)
        english_count = sum(item.classroom_type == "G" for item in classrooms)
        stat_cards = (
            [
                {"value": str(len(classrooms)), "label": "Aulas asignadas", "color": "#2f61da"},
                {"value": str(regular_count), "label": "Cursos regulares", "color": "#168a5b"},
                {"value": str(english_count), "label": "Grupos de inglés", "color": "#7656c9"},
            ]
            if integration_error is None
            else []
        )
    elif _google_mode():
        aulas = []
        stat_cards = []
        classroom_notice = (
            "Tu identidad institucional está verificada. Para mostrar aulas y alumnos, "
            "CIMA debe habilitar un intercambio de tokens de Google con su API."
        )
    else:
        aulas = CLASSROOMS
        stat_cards = STAT_CARDS
    return (
        render_template(
            "dashboard.html",
            active_nav="tablon",
            user=current_user,
            stat_cards=stat_cards,
            aulas=aulas,
            today_label=date_label(now),
            periodo_range=period_label(now),
            demo_mode=current_app.config["DEMO_MODE"],
            official_mode=_official_mode(),
            google_mode=_google_mode(),
            integration_error=integration_error,
            classroom_notice=classroom_notice,
        ),
        response_status,
    )


@web_bp.get("/aulas/<int:classroom_id>")
@login_required
def classroom_detail(classroom_id: int):
    if not _official_mode():
        abort(404)
    classroom_type = (request.args.get("type") or "").strip().upper()
    order = (request.args.get("order") or "A").strip().upper()
    if classroom_type not in {"N", "G"} or order not in {"A", "N"}:
        abort(400)
    try:
        authorization, _teacher_id = current_cima_access()
        classrooms = _official_classrooms()
        classroom = next(
            (
                item
                for item in classrooms
                if item.institutional_id == str(classroom_id)
                and item.classroom_type == classroom_type
            ),
            None,
        )
        if classroom is None:
            abort(404)
        students = get_cima_client(current_app.config).list_students(
            authorization,
            classroom.institutional_id,
            classroom.classroom_type,
            order,
        )
    except CimaAuthenticationError:
        return _official_login_expired()
    except CimaAPIError as exc:
        current_app.logger.warning("CIMA classroom request failed: %s", type(exc).__name__)
        return (
            render_template(
                "integration_error.html",
                active_nav="tablon",
                user=current_user,
                message=_cima_error_message(exc),
            ),
            exc.status_code,
        )
    return render_template(
        "classroom_detail.html",
        active_nav="tablon",
        user=current_user,
        classroom=_classroom_card(classroom),
        students=students,
        order=order,
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
    integration_error = None
    integration_notice = None
    if _official_mode():
        try:
            classrooms = [
                {
                    "value": f"{item.institutional_id}:{item.classroom_type}",
                    "label": item.description,
                }
                for item in _official_classrooms()
            ]
        except CimaAuthenticationError:
            return _official_login_expired()
        except CimaAPIError as exc:
            classrooms = []
            integration_error = _cima_error_message(exc)
    elif _google_mode():
        classrooms = []
        integration_notice = (
            "La cuenta Google está activa, pero CIMA aún no ofrece un intercambio "
            "documentado para consultar las aulas sin contraseña."
        )
    else:
        classrooms = [{"value": item["name"], "label": item["name"]} for item in CLASSROOMS]
    return render_template(
        "sesiones.html",
        active_nav="sesiones",
        user=current_user,
        sessions=sessions,
        classrooms=classrooms,
        demo_mode=current_app.config["DEMO_MODE"],
        integration_error=integration_error,
        integration_notice=integration_notice,
    )


@web_bp.post("/sesiones/nueva")
@login_required
@limiter.limit("20 per hour")
def create_session():
    title = (request.form.get("title") or "").strip()
    classroom = (request.form.get("classroom") or "").strip()
    scheduled_raw = (request.form.get("scheduled_at") or "").strip()
    official_classroom = None
    if _official_mode():
        try:
            available_classrooms = {
                f"{item.institutional_id}:{item.classroom_type}": item
                for item in _official_classrooms()
            }
        except CimaAuthenticationError:
            return _official_login_expired()
        except CimaAPIError as exc:
            flash(_cima_error_message(exc), "error")
            return redirect(url_for("web.sesiones"))
        official_classroom = available_classrooms.get(classroom)
        classroom_label = official_classroom.description if official_classroom else ""
    elif _google_mode():
        flash(
            "Las aulas oficiales todavía no están disponibles mediante el acceso de Google.",
            "error",
        )
        return redirect(url_for("web.sesiones"))
    else:
        valid_classrooms = {item["name"] for item in CLASSROOMS}
        classroom_label = classroom if classroom in valid_classrooms else ""
    if not title or len(title) > 120 or not classroom_label:
        flash("Completa correctamente el título y el aula.", "error")
        return redirect(url_for("web.sesiones"))
    try:
        scheduled_at = datetime.fromisoformat(scheduled_raw)
    except ValueError:
        flash("Selecciona una fecha y hora válidas.", "error")
        return redirect(url_for("web.sesiones"))

    learning_session = LearningSession(
        title=title,
        classroom=classroom_label,
        scheduled_at=scheduled_at,
        status="programada",
        owner_id=current_user.id,
    )
    db.session.add(learning_session)
    db.session.flush()
    if official_classroom is not None:
        db.session.add(
            CimaLearningSession(
                learning_session_id=learning_session.id,
                classroom_id=official_classroom.institutional_id,
                classroom_type=official_classroom.classroom_type,
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
