from extensions import db
from models import Interaccion, Material, TIPO_CUENTO


def add_material(owner, name):
    material = Material(
        nombre_material=name,
        tipo_material=TIPO_CUENTO,
        path_audio="fixtures/audio.wav",
        path_texto="fixtures/texto.txt",
        path_audio_resumen="fixtures/resumen.wav",
        path_texto_resumen="fixtures/resumen.txt",
        path_preguntas="fixtures/preguntas.json",
        fk_user=owner,
    )
    db.session.add(material)
    db.session.flush()
    return material


def add_interaction(material, student_id, *, correct, question, answer, appraisal):
    interaction = Interaccion(
        material=material,
        fk_alumno=student_id,
        pregunta=question,
        respuesta=answer,
        path_audio_rpta="fixtures/respuesta.wav",
        apreciacion_robot=appraisal,
        rpta_correcta=correct,
    )
    db.session.add(interaction)
    return interaction


def test_classroom_student_list_renders_adapter_students(client):
    response = client.get("/aulas/AULA-REAL-1")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Pérez Flores" in html
    assert "Ana Lucía" in html
    assert "Quispe Rojas" in html
    assert "/aulas/AULA-REAL-1/alumnos/ALU-TEST-1" in html


def test_teacher_cannot_open_a_classroom_that_is_not_theirs(client):
    response = client.get("/aulas/AULA-AJENA")

    assert response.status_code == 404
    assert "no pertenece a la docente autenticada" in response.get_data(as_text=True)


def test_progress_shows_results_and_ignores_other_teacher_materials(app, client):
    with app.app_context():
        own_material = add_material("DOC-TEST-1", "Cuento autorizado")
        other_material = add_material("DOC-OTRA", "Material ajeno")
        add_interaction(
            own_material,
            "ALU-TEST-1",
            correct=True,
            question="Pregunta correcta",
            answer="Respuesta correcta",
            appraisal="Muy bien.",
        )
        add_interaction(
            own_material,
            "ALU-TEST-1",
            correct=False,
            question="Pregunta incorrecta",
            answer="Respuesta incorrecta",
            appraisal="Debe intentarlo otra vez.",
        )
        add_interaction(
            other_material,
            "ALU-TEST-1",
            correct=True,
            question="Pregunta privada",
            answer="Respuesta privada",
            appraisal="No debe mostrarse.",
        )
        db.session.commit()

    response = client.get("/aulas/AULA-REAL-1/avance")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "✓" in html
    assert "✕" in html
    assert "1/2" in html
    assert "Material ajeno" not in html


def test_student_detail_shows_question_answer_and_robot_appraisal(app, client):
    with app.app_context():
        material = add_material("DOC-TEST-1", "El bosque que escucha")
        add_interaction(
            material,
            "ALU-TEST-1",
            correct=True,
            question="¿Qué hizo Luna para ayudar?",
            answer="Escuchó a sus amigos.",
            appraisal="Respuesta clara y completa.",
        )
        db.session.commit()

    response = client.get("/aulas/AULA-REAL-1/alumnos/ALU-TEST-1")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "¿Qué hizo Luna para ayudar?" in html
    assert "Escuchó a sus amigos." in html
    assert "Respuesta clara y completa." in html
    assert "El bosque que escucha" in html


def test_saving_sentence_material_uses_only_path_preguntas(app, client):
    sentence_text = "La luna brilla.\nEl río canta."
    response = client.post(
        "/api/material/save",
        data={
            "tipo_material": "oracion",
            "title": "Oraciones de práctica",
            "sentences_text": sentence_text,
        },
    )

    assert response.status_code == 200
    with app.app_context():
        material = db.session.get(Material, response.get_json()["material_id"])
        assert material.tipo_material == "oracion"
        assert material.path_preguntas == sentence_text
        assert material.path_texto is None
        assert material.path_texto_resumen is None
        assert material.path_audio is None
        assert material.path_audio_resumen is None
