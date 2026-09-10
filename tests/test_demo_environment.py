import io
import json
import tempfile
import wave
from datetime import date, timedelta

import pytest

import app as app_module
from extensions import db
from models import Material, Periodo, Tema
from services.demo import DEMO_CLASSROOMS, DemoInstitutionalClient


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
        "UPLOADS_ROOT": tempfile.mkdtemp(prefix="maxcim-demo-uploads-"),
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


def test_each_demo_classroom_has_fictional_students():
    institutional_client = DemoInstitutionalClient()

    for classroom in DEMO_CLASSROOMS:
        students = institutional_client.list_classroom_students(
            "maxcim-demo-only-token", classroom.institutional_id
        )
        assert students
        assert all(student.institutional_id.startswith("ALU-DEMO-") for student in students)


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


def test_demo_ai_sentence_draft_generates_without_gemini(demo_client):
    enter_demo(demo_client)
    draft = demo_client.post("/api/sentences/generate", json={
        "topic": "los animales de la granja",
        "grade_level": "tercero de primaria",
        "count": 6,
    })
    assert draft.status_code == 200
    data = draft.get_json()
    assert data["title"] == "Oraciones: los animales de la granja"
    assert len(data["sentences"]) == 6
    assert all(isinstance(sentence, str) and sentence for sentence in data["sentences"])

    # "Generar 5 con IA" desde la revisión: sin tema, con oraciones previas que
    # no deben repetirse en la respuesta.
    more = demo_client.post("/api/sentences/generate", json={
        "count": 5,
        "existing": data["sentences"],
    })
    assert more.status_code == 200
    added = more.get_json()["sentences"]
    assert added
    assert not (set(s.casefold() for s in added) & set(s.casefold() for s in data["sentences"]))


def test_demo_image_sentence_draft_has_two_nouns_each(demo_client):
    enter_demo(demo_client)
    draft = demo_client.post("/api/sentences/generate-images", json={
        "topic": "las profesiones",
        "grade_level": "segundo de primaria",
        "count": 6,
    })
    assert draft.status_code == 200
    data = draft.get_json()
    assert data["title"] == "Oraciones con imágenes: las profesiones"
    assert len(data["items"]) == 6
    for item in data["items"]:
        assert item["texto"].strip()
        assert len(item["sustantivos"]) == 2
        assert all(noun.strip() for noun in item["sustantivos"])


def test_demo_sentence_material_is_identified_and_saved_as_a_list(
    demo_app, demo_client, tmp_path, monkeypatch
):
    monkeypatch.setitem(demo_app.config, "UPLOADS_ROOT", str(tmp_path))
    enter_demo(demo_client)
    document = (
        "El perro corre en el parque.\n"
        "La maestra lee un cuento. Los niños escuchan con atención.\n"
    )

    processed = demo_client.post(
        "/api/material/process",
        data={
            "tipo_material": "oracion",
            "title": "Oraciones de práctica",
            "file": (io.BytesIO(document.encode("utf-8")), "oraciones.txt"),
        },
        content_type="multipart/form-data",
    )
    assert processed.status_code == 200
    sentences = processed.get_json()["sentences"]
    assert sentences == [
        "El perro corre en el parque.",
        "La maestra lee un cuento.",
        "Los niños escuchan con atención.",
    ]

    with demo_app.app_context():
        periodo = Periodo(
            nombre="I BIMESTRE", anio=date.today().year,
            fecha_inicio=date.today() - timedelta(days=1),
            fecha_fin=date.today() + timedelta(days=1),
        )
        db.session.add(periodo)
        db.session.commit()
        tema = Tema(nombre="Animales", fk_user="DOC-DEMO-01", id_periodo=periodo.id)
        db.session.add(tema)
        db.session.commit()
        periodo_id, tema_id = periodo.id, tema.id

    saved = demo_client.post(
        "/api/material/save",
        data={
            "tipo_material": "oracion",
            "title": "Oraciones de práctica",
            "sentences_json": json.dumps(sentences),
            "id_periodo": str(periodo_id),
            "id_tema": str(tema_id),
        },
    )
    assert saved.status_code == 200
    material_id = saved.get_json()["material_id"]

    robot_view = demo_client.get(
        f"/api/materials/{material_id}?teacher_id=DOC-DEMO-01"
    )
    assert robot_view.get_json()["oraciones"] == sentences

    page = demo_client.get("/material").get_data(as_text=True)
    assert "El perro corre en el parque." in page
    assert "3 oraciones" in page


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

    audio_buffer = io.BytesIO()
    with wave.open(audio_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 1600)
    audio_buffer.seek(0)

    created = demo_client.post("/api/interacciones", data={
        "id_material": str(material_id),
        "fk_alumno": "ALU-DEMO-1042",
        "pregunta": "¿Qué aprendiste hoy?",
        "respuesta": "Aprendí a escuchar antes de responder.",
        "apreciacion_robot": "Excelente participación.",
        "rpta_correcta": "true",
        "audio_rpta": (audio_buffer, "respuesta.wav"),
    })
    assert created.status_code == 201
    assert created.get_json()["fk_alumno"] == "ALU-DEMO-1042"

    listed = demo_client.get(
        f"/api/interacciones?teacher_id=DOC-DEMO-01&id_material={material_id}"
    )
    assert listed.status_code == 200
    assert len(listed.get_json()) == 1
    assert listed.get_json()[0]["rpta_correcta"] is True
