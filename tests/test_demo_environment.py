import io
import wave

import pytest

import app as app_module
from extensions import db
from models import Material


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


def test_demo_can_register_and_list_interactions(demo_app, demo_client):
    enter_demo(demo_client)
    with demo_app.app_context():
        material = Material(
            nombre_material="El bosque que escucha",
            tipo_material="general",
            path_audio="fixtures/audio.wav",
            path_texto="fixtures/texto.txt",
            path_audio_resumen="fixtures/resumen.wav",
            path_texto_resumen="fixtures/resumen.txt",
            path_preguntas="fixtures/preguntas.json",
            fk_user="DOC-DEMO-01",
        )
        db.session.add(material)
        db.session.commit()
        material_id = material.id

    created = demo_client.post("/api/interacciones", json={
        "id_material": material_id,
        "fk_alumno": "ALU-DEMO-1042",
        "pregunta": "¿Qué aprendiste hoy?",
        "respuesta": "Aprendí a escuchar antes de responder.",
        "path_audio_rpta": "uploads/demo/respuesta.wav",
        "apreciacion_robot": "Excelente participación.",
        "rpta_correcta": True,
    })
    assert created.status_code == 201
    assert created.get_json()["fk_alumno"] == "ALU-DEMO-1042"

    listed = demo_client.get(f"/api/interacciones?id_material={material_id}")
    assert listed.status_code == 200
    assert len(listed.get_json()) == 1
    assert listed.get_json()[0]["rpta_correcta"] is True
