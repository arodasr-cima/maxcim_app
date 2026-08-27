"""Fictional data used exclusively by the demonstration environment."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .extensions import db
from .models import LearningSession, Material, User
from .services.ai import demo_wav
from .services.storage import write_bundle

MATERIAL_SKILLS = [
    "Todas las habilidades",
    "Comunicación oral",
    "Escucha activa",
    "Empatía",
    "Trabajo en equipo",
    "Resolución de conflictos",
]

CLASSROOMS = [
    {
        "name": "3.º A — Secundaria",
        "grade": "Tercero de Secundaria",
        "tutor": "Docente Demo",
        "initials": "3A",
        "avatar_bg": "#2f61da",
        "score": 82,
        "pendientes": 2,
        "skills": [
            {"name": "Comunicación oral", "value": 85, "color": "#2f61da"},
            {"name": "Escucha activa", "value": 76, "color": "#168a5b"},
            {"name": "Trabajo en equipo", "value": 84, "color": "#b8760a"},
        ],
    },
    {
        "name": "1.º B — Secundaria",
        "grade": "Primero de Secundaria",
        "tutor": "Docente Demo",
        "initials": "1B",
        "avatar_bg": "#168a5b",
        "score": 74,
        "pendientes": 4,
        "skills": [
            {"name": "Empatía", "value": 70, "color": "#2f61da"},
            {"name": "Comunicación oral", "value": 79, "color": "#168a5b"},
            {"name": "Resolución de conflictos", "value": 72, "color": "#b8760a"},
        ],
    },
    {
        "name": "4.º C — Secundaria",
        "grade": "Cuarto de Secundaria",
        "tutor": "Docente Demo",
        "initials": "4C",
        "avatar_bg": "#b8760a",
        "score": 88,
        "pendientes": 1,
        "skills": [
            {"name": "Trabajo en equipo", "value": 90, "color": "#2f61da"},
            {"name": "Escucha activa", "value": 86, "color": "#168a5b"},
            {"name": "Comunicación oral", "value": 88, "color": "#b8760a"},
        ],
    },
    {
        "name": "2.º A — Secundaria",
        "grade": "Segundo de Secundaria",
        "tutor": "Docente Demo",
        "initials": "2A",
        "avatar_bg": "#7656c9",
        "score": 69,
        "pendientes": 5,
        "skills": [
            {"name": "Empatía", "value": 65, "color": "#2f61da"},
            {"name": "Comunicación oral", "value": 71, "color": "#168a5b"},
            {"name": "Escucha activa", "value": 70, "color": "#b8760a"},
        ],
    },
]

STAT_CARDS = [
    {"value": "4", "label": "Aulas a cargo", "color": "#2f61da"},
    {"value": "12", "label": "Evaluaciones pendientes", "color": "#c43f4e"},
    {"value": "78%", "label": "Promedio general", "color": "#168a5b"},
    {"value": "146", "label": "Estudiantes evaluados", "color": "#17356f"},
]


def local_now(app) -> datetime:
    return datetime.now(ZoneInfo(app.config["DISPLAY_TIMEZONE"]))


def period_label(now: datetime) -> str:
    last_day = calendar.monthrange(now.year, now.month)[1]
    return f"01/{now.month:02d}/{now.year} – {last_day:02d}/{now.month:02d}/{now.year}"


def date_label(now: datetime) -> str:
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    months = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    return f"{days[now.weekday()]} {now.day} de {months[now.month - 1]}"


def seed_demo_data(app, force: bool = False) -> None:
    email = app.config["DEMO_EMAIL"].lower()
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(email=email, display_name="Docente Demo", initials="DD", role="DOCENTE")
        user.set_password(app.config["DEMO_PASSWORD"])
        db.session.add(user)
        db.session.flush()
    elif force:
        user.set_password(app.config["DEMO_PASSWORD"])

    if not LearningSession.query.filter_by(owner_id=user.id).first():
        now = local_now(app).replace(tzinfo=None, second=0, microsecond=0)
        db.session.add_all(
            [
                LearningSession(
                    title="Escucha activa mediante relatos",
                    classroom="3.º A — Secundaria",
                    scheduled_at=now + timedelta(days=1),
                    status="programada",
                    owner_id=user.id,
                ),
                LearningSession(
                    title="Resolución colaborativa de conflictos",
                    classroom="1.º B — Secundaria",
                    scheduled_at=now - timedelta(days=2),
                    status="completada",
                    owner_id=user.id,
                ),
            ]
        )

    if not Material.query.filter_by(owner_id=user.id).first():
        text = (
            "En el aula, Luna notó que su compañero quería compartir una idea. "
            "Guardó silencio, lo miró con atención y esperó a que terminara. "
            "Después, ambos unieron sus propuestas y resolvieron el reto juntos."
        )
        summary = (
            "Luna practica la escucha activa y coopera con su compañero para resolver "
            "un reto mediante el diálogo."
        )
        questions = [
            {"tipo": "literal", "pregunta": "¿Qué hizo Luna cuando su compañero quiso hablar?"},
            {"tipo": "inferencial", "pregunta": "¿Cómo ayudó la escucha activa a resolver el reto?"},
            {"tipo": "critica", "pregunta": "¿Cómo aplicarías esta actitud en tu aula?"},
        ]
        paths = write_bundle(
            app.config["UPLOAD_FOLDER"],
            text,
            summary,
            questions,
            demo_wav(text),
            demo_wav(summary),
        )
        db.session.add(
            Material(
                nombre_material="El poder de escuchar",
                skill="Escucha activa",
                path_audio=paths.audio,
                path_texto=paths.text,
                path_audio_resumen=paths.summary_audio,
                path_texto_resumen=paths.summary,
                path_preguntas=paths.questions,
                owner_id=user.id,
            )
        )

    db.session.commit()
