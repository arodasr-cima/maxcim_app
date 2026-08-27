import json

import app as app_module
from extensions import db
from models import EventoReconocimiento, Material, Pregunta, SesionInteraccion


def seed_material():
    material = Material(
        nombre_material="El bosque que escucha",
        path_audio="demo/audio.wav",
        path_texto="demo/texto.txt",
        path_audio_resumen="demo/resumen.wav",
        path_texto_resumen="demo/resumen.txt",
        path_preguntas="demo/preguntas.json",
        fk_user=str(app_module.USER["fk_user"]),
    )
    db.session.add(material)
    db.session.flush()
    question = Pregunta(
        id_material=material.id,
        tipo="literal",
        enunciado="¿Qué hizo Luna para ayudar?",
        respuesta_esperada="Escuchó a su amiga sin interrumpir.",
        orden=1,
        estado="aprobada",
        aprobada_por=str(app_module.USER["fk_user"]),
    )
    db.session.add(question)
    db.session.commit()
    return material, question


def create_session(client, material_id):
    response = client.post("/api/interactions/sessions", json={
        "classroom_id": "demo-3ro-a",
        "material_id": material_id,
        "objective": "Practicar escucha activa",
    })
    assert response.status_code == 201
    return response.get_json()


def identify_student(client, session_uuid, confidence=0.97):
    return client.post("/api/integrations/face-recognition/events", json={
        "session_uuid": session_uuid,
        "person_id": "ALU-1042",
        "person_type": "ALUMNO",
        "display_name": "Valeria Mendoza",
        "confidence": confidence,
    })


def test_full_oral_interaction_requires_teacher_approval(app, client):
    with app.app_context():
        material, question = seed_material()
        material_id = material.id
        question_id = question.id

    session = create_session(client, material_id)
    session_uuid = session["uuid"]
    assert session["status"] == "esperando_identificacion"

    low_confidence = identify_student(client, session_uuid, confidence=0.70)
    assert low_confidence.status_code == 202
    assert low_confidence.get_json()["event_status"] == "requiere_confirmacion"
    assert low_confidence.get_json()["session"]["student_id"] is None

    recognized = identify_student(client, session_uuid)
    assert recognized.status_code == 200
    assert recognized.get_json()["session"]["status"] == "activa"
    assert recognized.get_json()["session"]["student_id"] == "ALU-1042"

    robot_payload = client.get(f"/api/interactions/sessions/{session_uuid}/robot-payload")
    assert robot_payload.status_code == 200
    assert robot_payload.get_json()["material"]["questions"] == [{
        "expected_answer": "Escuchó a su amiga sin interrumpir.",
        "id": question_id,
        "order": 1,
        "statement": "¿Qué hizo Luna para ayudar?",
        "type": "literal",
    }]

    maxcim_turn = client.post(f"/api/interactions/sessions/{session_uuid}/turns", json={
        "speaker": "MAXCIM",
        "transcript": "¿Qué hizo Luna para ayudar?",
        "question_id": question_id,
    })
    assert maxcim_turn.status_code == 201

    student_turn = client.post(f"/api/interactions/sessions/{session_uuid}/turns", json={
        "speaker": "ALUMNO",
        "transcript": "La escuchó y esperó a que terminara.",
        "question_id": question_id,
        "response_time_ms": 4100,
        "is_correct": True,
        "needed_help": False,
    })
    assert student_turn.status_code == 201

    completed = client.post(f"/api/interactions/sessions/{session_uuid}/complete")
    assert completed.status_code == 200
    evaluation = completed.get_json()["evaluation"]
    assert evaluation["participation_percentage"] == 100.0
    assert evaluation["comprehension_percentage"] == 100.0
    assert evaluation["overall_percentage"] == 100.0
    assert evaluation["status"] == "pendiente_ia"

    approved = client.patch(f"/api/interactions/sessions/{session_uuid}/evaluation", json={
        "participation_percentage": 95,
        "comprehension_percentage": 90,
        "oral_interaction_percentage": 88,
        "overall_percentage": 91,
        "teacher_feedback": "Se expresó con claridad; reforzar el respeto de turnos.",
    })
    assert approved.status_code == 200
    result = approved.get_json()
    assert result["status"] == "evaluacion_aprobada"
    assert result["teacher_reviewed"] is True
    assert result["evaluation"]["overall_percentage"] == 91.0
    assert result["evaluation"]["status"] == "aprobada"

    with app.app_context():
        events = EventoReconocimiento.query.all()
        assert [event.estado for event in events] == ["requiere_confirmacion", "aceptado"]
        assert all(not hasattr(event, "embedding") for event in events)


def test_recognized_personnel_does_not_start_student_session(app, client):
    with app.app_context():
        material, _ = seed_material()
        material_id = material.id

    session_uuid = create_session(client, material_id)["uuid"]
    response = client.post("/api/integrations/face-recognition/events", json={
        "session_uuid": session_uuid,
        "person_id": "DOC-77",
        "person_type": "DOCENTE",
        "display_name": "María Rojas",
        "confidence": 0.99,
    })
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["event_status"] == "ignorado"
    assert payload["session"]["status"] == "esperando_identificacion"


def test_robot_payload_supports_free_conversation(client):
    response = client.post("/api/interactions/sessions", json={
        "classroom_id": "demo-3ro-a",
        "material_id": None,
        "objective": "Practicar una presentación personal",
    })
    assert response.status_code == 201
    session_uuid = response.get_json()["uuid"]
    assert identify_student(client, session_uuid).status_code == 200

    payload = client.get(f"/api/interactions/sessions/{session_uuid}/robot-payload")
    assert payload.status_code == 200
    assert payload.get_json()["material"] is None
    assert payload.get_json()["objective"] == "Practicar una presentación personal"


def test_turn_rejects_question_from_another_material(app, client):
    with app.app_context():
        material, _ = seed_material()
        other = Material(
            nombre_material="Otro cuento",
            path_audio="other/audio.wav",
            path_texto="other/texto.txt",
            path_audio_resumen="other/resumen.wav",
            path_texto_resumen="other/resumen.txt",
            path_preguntas="other/preguntas.json",
            fk_user=str(app_module.USER["fk_user"]),
        )
        db.session.add(other)
        db.session.flush()
        other_question = Pregunta(
            id_material=other.id,
            tipo="literal",
            enunciado="¿Pregunta ajena?",
            respuesta_esperada="No corresponde.",
            orden=1,
            estado="aprobada",
        )
        db.session.add(other_question)
        db.session.commit()
        material_id = material.id
        other_question_id = other_question.id

    session_uuid = create_session(client, material_id)["uuid"]
    assert identify_student(client, session_uuid).status_code == 200
    response = client.post(f"/api/interactions/sessions/{session_uuid}/turns", json={
        "speaker": "MAXCIM",
        "transcript": "¿Pregunta ajena?",
        "question_id": other_question_id,
    })
    assert response.status_code == 400


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


def test_robot_webhook_requires_secret_outside_demo(monkeypatch):
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
        session = SesionInteraccion(
            uuid="4cd0de9b-9b41-4b8b-8cf9-c4ffb98bcfd2",
            id_docente_institucional="DOC-1",
            id_aula_institucional="AULA-1",
            objetivo="Conversar",
        )
        db.session.add(session)
        db.session.commit()

    client = application.test_client()
    payload = {
        "session_uuid": "4cd0de9b-9b41-4b8b-8cf9-c4ffb98bcfd2",
        "person_id": "ALU-1",
        "person_type": "ALUMNO",
        "confidence": 0.95,
        "classroom_ids": ["AULA-1"],
    }
    assert client.post("/api/integrations/face-recognition/events", json=payload).status_code == 401
    accepted = client.post(
        "/api/integrations/face-recognition/events",
        json=payload,
        headers={"X-MAXCIM-Webhook-Secret": "robot-secret"},
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["event_status"] == "aceptado"

    with application.app_context():
        db.session.remove()
        db.drop_all()
