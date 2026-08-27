import io
import wave

import pytest

import app as app_module
from extensions import db


@pytest.fixture()
def demo_app(monkeypatch):
    monkeypatch.setattr(app_module, "gemini_client", None)
    application = app_module.create_app({
        "TESTING": True,
        "DEMO_MODE": True,
        "SECRET_KEY": "",
        "SESSION_TOKEN_ENCRYPTION_KEY": "",
        "SESSION_COOKIE_SECURE": False,
        "MAXCIM_WEBHOOK_SECRET": "",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
    })
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def demo_client(demo_app):
    return demo_app.test_client()


def enter_demo(demo_client):
    response = demo_client.get("/login/google")
    assert response.status_code == 302
    assert response.location == "/dashboard"


def test_demo_login_is_enabled_and_clearly_isolated(demo_client):
    page = demo_client.get("/login")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Entorno de pruebas" in html
    assert "Entrar como docente de prueba" in html
    assert 'value="DOC-DEMO-01"' in html

    enter_demo(demo_client)
    dashboard = demo_client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "PRUEBAS" in dashboard.get_data(as_text=True)
    assert "3RO A — Tutoría" in dashboard.get_data(as_text=True)
    assert demo_client.get("/health").get_json() == {
        "status": "ok",
        "environment": "test",
    }


def test_demo_accepts_prefilled_id_credentials(demo_client):
    response = demo_client.post("/login", data={
        "institutional_id": "DOC-PRUEBA-LIBRE",
        "credential": "cualquier-valor",
    })
    assert response.status_code == 302
    assert response.location == "/dashboard"
    dashboard = demo_client.get("/dashboard").get_data(as_text=True)
    assert "DOC-PRUEBA-LIBRE" in dashboard


def test_demo_story_questions_and_audio_work_without_gemini(demo_client):
    enter_demo(demo_client)
    story = demo_client.post("/api/story/generate", json={
        "character": "una zorrita llamada Luna",
        "setting": "un bosque mágico",
        "grade_level": "tercero de primaria",
        "objective": "escuchar antes de responder",
        "extra_details": "un puente de colores",
        "duration_minutes": 2,
    })
    assert story.status_code == 200
    story_data = story.get_json()
    assert story_data["target_duration_minutes"] == 2
    assert story_data["word_count"] == 250

    questions = demo_client.post("/api/material/questions", json={
        "text": story_data["story"],
        "counts": {"literales": 2, "inferenciales": 1, "criticas": 1},
    })
    assert questions.status_code == 200
    assert len(questions.get_json()["questions"]["literales"]) == 2

    audio = demo_client.post("/api/material/tts", json={
        "text": story_data["story"],
        "target_duration_minutes": 1,
    })
    assert audio.status_code == 200
    assert audio.headers["X-MAXCIM-Demo-Audio"] == "true"
    assert audio.headers["X-MAXCIM-Audio-Duration-Seconds"] == "60.00"
    with wave.open(io.BytesIO(audio.data), "rb") as wav_file:
        assert wav_file.getnframes() / wav_file.getframerate() == 60


def test_demo_can_simulate_the_complete_oral_flow(demo_client):
    enter_demo(demo_client)
    created = demo_client.post("/api/interactions/sessions", json={
        "classroom_id": "AULA-DEMO-3A",
        "material_id": None,
        "objective": "Practicar la escucha activa",
    })
    assert created.status_code == 201
    session_uuid = created.get_json()["uuid"]

    recognized = demo_client.post("/api/integrations/face-recognition/events", json={
        "session_uuid": session_uuid,
        "person_id": "ALU-DEMO-1042",
        "confidence": 0.97,
    })
    assert recognized.status_code == 200
    assert recognized.get_json()["session"]["student_name"] == "Valeria Mendoza"

    for turn in (
        {"speaker": "MAXCIM", "transcript": "¿Qué aprendiste hoy?"},
        {
            "speaker": "ALUMNO",
            "transcript": "Aprendí a escuchar antes de responder.",
            "response_time_ms": 3200,
            "is_correct": True,
        },
    ):
        response = demo_client.post(
            f"/api/interactions/sessions/{session_uuid}/turns",
            json=turn,
        )
        assert response.status_code == 201

    completed = demo_client.post(f"/api/interactions/sessions/{session_uuid}/complete")
    assert completed.status_code == 200
    evaluation = completed.get_json()["evaluation"]
    assert evaluation["status"] == "pendiente_revision"
    assert evaluation["oral_interaction_percentage"] == 100

    approved = demo_client.patch(
        f"/api/interactions/sessions/{session_uuid}/evaluation",
        json={
            "participation_percentage": 95,
            "comprehension_percentage": 92,
            "oral_interaction_percentage": 90,
            "overall_percentage": 92,
            "teacher_feedback": "Buen trabajo en la prueba.",
        },
    )
    assert approved.status_code == 200
    assert approved.get_json()["status"] == "evaluacion_aprobada"
