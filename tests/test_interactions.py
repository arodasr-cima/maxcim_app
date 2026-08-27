import json

import app as app_module
from extensions import db
from models import Interaccion, Material, TIPO_CUENTO, TIPO_ORACION


TEST_TEACHER_ID = "DOC-TEST-1"


def seed_material(**overrides):
    defaults = dict(
        nombre_material="El bosque que escucha",
        tipo_material=TIPO_CUENTO,
        path_audio="fixtures/audio.wav",
        path_texto="fixtures/texto.txt",
        path_audio_resumen="fixtures/resumen.wav",
        path_texto_resumen="fixtures/resumen.txt",
        path_preguntas="fixtures/preguntas.json",
        fk_user=TEST_TEACHER_ID,
    )
    defaults.update(overrides)
    material = Material(**defaults)
    db.session.add(material)
    db.session.commit()
    return material


def register_interaction(client, material_id, **overrides):
    payload = {
        "id_material": material_id,
        "fk_alumno": "ALU-TEST-1",
        "pregunta": "¿Qué hizo Luna para ayudar?",
        "respuesta": "La escuchó y esperó a que terminara.",
        "path_audio_rpta": "uploads/test/respuesta.wav",
        "apreciacion_robot": "Respuesta clara y completa.",
        "rpta_correcta": True,
    }
    payload.update(overrides)
    return client.post("/api/interacciones", json=payload)


def test_registrar_interaccion_creates_a_record(app, client):
    with app.app_context():
        material_id = seed_material().id

    response = register_interaction(client, material_id)
    assert response.status_code == 201
    data = response.get_json()
    assert data["id_material"] == material_id
    assert data["fk_alumno"] == "ALU-TEST-1"
    assert data["rpta_correcta"] is True

    with app.app_context():
        assert Interaccion.query.count() == 1


def test_registrar_interaccion_requires_all_fields(app, client):
    with app.app_context():
        material_id = seed_material().id

    response = register_interaction(client, material_id, pregunta="")
    assert response.status_code == 400
    assert "pregunta" in response.get_json()["error"]


def test_registrar_interaccion_rejects_an_invalid_bool(app, client):
    with app.app_context():
        material_id = seed_material().id

    response = register_interaction(client, material_id, rpta_correcta="tal vez")
    assert response.status_code == 400


def test_registrar_interaccion_rejects_unknown_material(client):
    response = register_interaction(client, 999999)
    assert response.status_code == 404


def test_registrar_interaccion_requires_webhook_secret_in_production(monkeypatch):
    monkeypatch.setattr(app_module, "gemini_client", None)
    application = app_module.create_app({
        "TESTING": False,
        "DEMO_MODE": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "MAXCIM_WEBHOOK_SECRET": "robot-secret",
    })
    with application.app_context():
        db.create_all()
        material_id = seed_material().id

    test_client = application.test_client()
    payload = {
        "id_material": material_id,
        "fk_alumno": "ALU-TEST-1",
        "pregunta": "¿Qué aprendiste?",
        "respuesta": "A escuchar antes de responder.",
        "path_audio_rpta": "uploads/test/respuesta.wav",
        "apreciacion_robot": "Bien hecho.",
        "rpta_correcta": True,
    }
    assert test_client.post("/api/interacciones", json=payload).status_code == 401
    accepted = test_client.post(
        "/api/interacciones",
        json=payload,
        headers={"X-MAXCIM-Webhook-Secret": "robot-secret"},
    )
    assert accepted.status_code == 201

    with application.app_context():
        db.session.remove()
        db.drop_all()


def test_list_interacciones_filters_by_material_and_alumno(app, client):
    with app.app_context():
        material_id = seed_material().id
        other_material_id = seed_material(nombre_material="Otro cuento").id

    register_interaction(client, material_id, fk_alumno="ALU-A")
    register_interaction(client, material_id, fk_alumno="ALU-B")
    register_interaction(client, other_material_id, fk_alumno="ALU-A")

    by_material = client.get(f"/api/interacciones?id_material={material_id}")
    assert by_material.status_code == 200
    assert len(by_material.get_json()) == 2

    by_alumno = client.get("/api/interacciones?fk_alumno=ALU-A")
    assert by_alumno.status_code == 200
    assert len(by_alumno.get_json()) == 2

    both = client.get(f"/api/interacciones?id_material={material_id}&fk_alumno=ALU-A")
    assert both.status_code == 200
    assert len(both.get_json()) == 1


def test_get_cuento_material_round_trips_through_robot_api(
    app, client, tmp_path, monkeypatch
):
    material_dir = tmp_path / "material"
    material_dir.mkdir()
    questions = [{"pregunta": "¿Quién es el personaje?", "respuesta_esperada": "Luna"}]
    (material_dir / "preguntas.json").write_text(
        json.dumps(questions, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(app, "static_folder", str(tmp_path))

    with app.app_context():
        material = seed_material(
            tipo_material=TIPO_CUENTO,
            path_texto="material/texto.txt",
            path_texto_resumen="material/resumen.txt",
            path_audio="material/audio.wav",
            path_audio_resumen="material/audio_resumen.wav",
            path_preguntas="material/preguntas.json",
        )
        material_id = material.id
        fecha_subido = material.fecha_subido.isoformat()

    response = client.get(f"/api/materials/{material_id}")
    assert response.status_code == 200
    assert response.get_json() == {
        "id": material_id,
        "titulo": "El bosque que escucha",
        "tipo_material": TIPO_CUENTO,
        "fecha_subido": fecha_subido,
        "fk_user": TEST_TEACHER_ID,
        "texto_completo_url": "http://localhost/static/material/texto.txt",
        "texto_resumen_url": "http://localhost/static/material/resumen.txt",
        "audio_completo_url": "http://localhost/static/material/audio.wav",
        "audio_resumen_url": "http://localhost/static/material/audio_resumen.wav",
        "preguntas_url": "http://localhost/static/material/preguntas.json",
        "preguntas": questions,
    }


def test_get_oracion_material_round_trips_through_robot_api(app, client):
    sentence_text = "La luna brilla.\nEl río canta."
    with app.app_context():
        material = seed_material(
            nombre_material="Oraciones de práctica",
            tipo_material=TIPO_ORACION,
            path_preguntas=sentence_text,
            path_texto=None,
            path_texto_resumen=None,
            path_audio=None,
            path_audio_resumen=None,
        )
        material_id = material.id
        fecha_subido = material.fecha_subido.isoformat()

    response = client.get(f"/api/materials/{material_id}")
    assert response.status_code == 200
    assert response.get_json() == {
        "id": material_id,
        "titulo": "Oraciones de práctica",
        "tipo_material": TIPO_ORACION,
        "fecha_subido": fecha_subido,
        "fk_user": TEST_TEACHER_ID,
        "oraciones": sentence_text,
        "texto_completo_url": None,
        "texto_resumen_url": None,
        "audio_completo_url": None,
        "audio_resumen_url": None,
        "preguntas_url": None,
        "preguntas": [],
    }


def test_material_save_requires_reviewed_expected_answers(client):
    response = client.post(
        "/api/material/save",
        data={
            "title": "Cuento",
            "transcribed_text": "Texto del cuento",
            "summary_text": "Resumen",
            "questions_json": json.dumps([{
                "tipo": "literal",
                "pregunta": "¿Quién es el personaje?",
                "respuesta_esperada": "",
            }]),
        },
    )
    assert response.status_code == 400
    assert "respuesta esperada" in response.get_json()["error"]
