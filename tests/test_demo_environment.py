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


def test_demo_image_sentence_material_is_extracted_and_saved(
    demo_app, demo_client, tmp_path, monkeypatch
):
    monkeypatch.setitem(demo_app.config, "UPLOADS_ROOT", str(tmp_path))
    enter_demo(demo_client)
    document = (
        "Ese oso ama la miel.\n"
        "La niña dibuja una casa. El perro corre tras la pelota.\n"
    )

    processed = demo_client.post(
        "/api/material/process",
        data={
            "tipo_material": "oracion_imagen",
            "title": "Oraciones con imágenes",
            "file": (io.BytesIO(document.encode("utf-8")), "oraciones.txt"),
        },
        content_type="multipart/form-data",
    )
    assert processed.status_code == 200
    items = processed.get_json()["items"]
    assert items and "sentences" not in processed.get_json()
    for item in items:
        assert item["texto"].strip()
        assert len(item["sustantivos"]) == 2
        assert all(noun.strip() for noun in item["sustantivos"])

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
            "tipo_material": "oracion_imagen",
            "title": "Oraciones con imágenes",
            "sentences_json": json.dumps(items),
            "id_periodo": str(periodo_id),
            "id_tema": str(tema_id),
        },
    )
    assert saved.status_code == 200
    material_id = saved.get_json()["material_id"]

    robot_view = demo_client.get(
        f"/api/materials/{material_id}?teacher_id=DOC-DEMO-01"
    ).get_json()
    assert robot_view["tipo_material"] == "oracion_imagen"
    assert robot_view["oraciones"] == [item["texto"] for item in items]
    # Guardado sin `staging_token`: se conserva el texto y los sustantivos,
    # todavía sin imágenes (imagen_url None, plantilla == texto completo).
    detalle = robot_view["oraciones_detalle"]
    assert [d["oracion_completa"] for d in detalle] == [item["texto"] for item in items]
    for d, item in zip(detalle, items):
        assert d["plantilla"] == item["texto"]
        assert [s["palabra"] for s in d["sustantivos"]] == item["sustantivos"]
        assert all(s["imagen_url"] is None for s in d["sustantivos"])

    resource = demo_client.get(
        f"/api/materials/{material_id}/oraciones?teacher_id=DOC-DEMO-01"
    ).get_json()
    assert resource["oraciones_detalle"] == detalle

    only_images = demo_client.get(
        "/api/materials?teacher_id=DOC-DEMO-01&tipo=oracion_imagen"
    ).get_json()
    assert [m["id"] for m in only_images] == [material_id]

    page = demo_client.get("/material").get_data(as_text=True)
    assert items[0]["texto"] in page


def test_demo_image_sentence_design_flow_generates_and_exposes_images(
    demo_app, demo_client, tmp_path, monkeypatch
):
    monkeypatch.setitem(demo_app.config, "UPLOADS_ROOT", str(tmp_path))
    enter_demo(demo_client)

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

    verified = [
        {"texto": "Ese oso ama la miel.", "sustantivos": ["oso", "miel"]},
        {"texto": "La niña dibuja una casa.", "sustantivos": ["niña", "casa"]},
    ]

    prepared = demo_client.post(
        "/api/material/image-sentences/prepare",
        json={"title": "Oraciones con imágenes", "items": verified},
    )
    assert prepared.status_code == 200
    body = prepared.get_json()
    token = body["token"]
    assert body["items"][0]["plantilla"] == "Ese {{0}} ama la {{1}}."
    first_img_url = body["items"][0]["sustantivos"][0]["imagen_url"]

    # La imagen en revisión se sirve como PNG.
    img = demo_client.get(first_img_url)
    assert img.status_code == 200
    assert img.data.startswith(b"\x89PNG\r\n\x1a\n")

    # Regenerar una sola imagen devuelve una URL nueva (cache-busted).
    regen = demo_client.post(
        "/api/material/image-sentences/regenerate",
        json={"token": token, "sentence_index": 0, "noun_index": 1},
    )
    assert regen.status_code == 200
    assert "?v=" in regen.get_json()["imagen_url"]

    saved = demo_client.post(
        "/api/material/save",
        data={
            "tipo_material": "oracion_imagen",
            "title": "Oraciones con imágenes",
            "staging_token": token,
            "sentences_json": json.dumps([
                {**verified[0], "staging_index": 0},
                {**verified[1], "staging_index": 1},
            ]),
            "id_periodo": str(periodo_id),
            "id_tema": str(tema_id),
        },
    )
    assert saved.status_code == 200
    material_id = saved.get_json()["material_id"]

    robot_view = demo_client.get(
        f"/api/materials/{material_id}?teacher_id=DOC-DEMO-01"
    ).get_json()
    detalle = robot_view["oraciones_detalle"]
    assert detalle[0]["plantilla"] == "Ese {{0}} ama la {{1}}."
    img_url = detalle[0]["sustantivos"][0]["imagen_url"]
    assert img_url and "/imagen/0/0" in img_url

    got = demo_client.get(
        f"/api/materials/{material_id}/imagen/0/0?teacher_id=DOC-DEMO-01"
    )
    assert got.status_code == 200
    assert got.data.startswith(b"\x89PNG\r\n\x1a\n")

    # El staging se limpió al guardar.
    assert demo_client.get(first_img_url).status_code == 404


def _tiny_png(color) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color).save(buf, format="PNG")
    return buf.getvalue()


def test_image_sentence_upload_own_image_names_file_after_the_word(
    demo_app, demo_client, tmp_path, monkeypatch
):
    """La docente puede reemplazar, con su propio archivo, la imagen que
    Gemini generó para un sustantivo. El nombre/formato del archivo subido
    es indiferente (aquí sube un .jpg llamado cualquier_cosa.jpg); al
    aprobar el diseño, el archivo final se guarda como PNG y se nombra
    según el sustantivo ("pollo.png"), no por posición. Dos sustantivos
    iguales en oraciones distintas -pero con imágenes distintas- no deben
    pisarse: el segundo cae a "pollo-2.png"."""
    monkeypatch.setitem(demo_app.config, "UPLOADS_ROOT", str(tmp_path))
    enter_demo(demo_client)

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

    verified = [
        {"texto": "El pollo come maíz.", "sustantivos": ["pollo", "maíz"]},
        {"texto": "Otro pollo duerme en el nido.", "sustantivos": ["pollo", "nido"]},
    ]
    prepared = demo_client.post(
        "/api/material/image-sentences/prepare",
        json={"title": "Oraciones con imágenes", "items": verified},
    )
    assert prepared.status_code == 200
    body = prepared.get_json()
    token = body["token"]
    assert body["items"][0]["sustantivos"][0]["fuente"] == "ia"

    # Sube su propio archivo para el "pollo" de la primera oración: nombre y
    # formato de archivo arbitrarios (un .jpg con cualquier nombre).
    upload = demo_client.post(
        "/api/material/image-sentences/upload-image",
        data={
            "token": token,
            "sentence_index": "0",
            "noun_index": "0",
            "imagen": (io.BytesIO(_tiny_png((255, 0, 0))), "cualquier_cosa.jpg"),
        },
        content_type="multipart/form-data",
    )
    assert upload.status_code == 200
    assert upload.get_json()["fuente"] == "manual"

    # Rechaza un archivo que no es una imagen real, sin importar su nombre.
    bad_upload = demo_client.post(
        "/api/material/image-sentences/upload-image",
        data={
            "token": token,
            "sentence_index": "1",
            "noun_index": "1",
            "imagen": (io.BytesIO(b"esto no es una imagen"), "nido.png"),
        },
        content_type="multipart/form-data",
    )
    assert bad_upload.status_code == 400

    saved = demo_client.post(
        "/api/material/save",
        data={
            "tipo_material": "oracion_imagen",
            "title": "Oraciones con imágenes",
            "staging_token": token,
            "sentences_json": json.dumps([
                {**verified[0], "staging_index": 0},
                {**verified[1], "staging_index": 1},
            ]),
            "id_periodo": str(periodo_id),
            "id_tema": str(tema_id),
        },
    )
    assert saved.status_code == 200
    material_id = saved.get_json()["material_id"]

    with demo_app.app_context():
        material = db.session.get(Material, material_id)
        oraciones_path = tmp_path / material.path_preguntas.removeprefix("uploads/")
    oraciones = json.loads(oraciones_path.read_text(encoding="utf-8"))

    # El sustantivo subido a mano se nombró "pollo.png"; el segundo "pollo"
    # (generado por IA, imagen distinta) no lo pisa -cae a "pollo-2.png".
    assert oraciones[0]["sustantivos"][0]["imagen"] == "img/pollo.png"
    assert oraciones[1]["sustantivos"][0]["imagen"] == "img/pollo-2.png"
    img_dir = oraciones_path.parent / "img"
    assert (img_dir / "pollo.png").is_file()
    assert (img_dir / "pollo-2.png").is_file()
    # Son imágenes distintas: no se pisaron una a la otra.
    assert (img_dir / "pollo.png").read_bytes() != (img_dir / "pollo-2.png").read_bytes()


def test_image_sentence_save_rejects_items_without_two_nouns(client, periodo_tema):
    periodo_id, tema_id = periodo_tema()
    bad = client.post(
        "/api/material/save",
        data={
            "tipo_material": "oracion_imagen",
            "title": "Oraciones con imágenes",
            "sentences_json": json.dumps([{"texto": "Un texto suelto.", "sustantivos": ["gato"]}]),
            "id_periodo": str(periodo_id),
            "id_tema": str(tema_id),
        },
    )
    assert bad.status_code == 400

    empty = client.post(
        "/api/material/save",
        data={
            "tipo_material": "oracion_imagen",
            "title": "Oraciones con imágenes",
            "sentences_json": "not-json",
            "id_periodo": str(periodo_id),
            "id_tema": str(tema_id),
        },
    )
    assert empty.status_code == 400


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
