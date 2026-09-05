import json

import pytest

from extensions import db
from models import Material, TIPO_CUENTO, TIPO_ORACION


TEACHER = "70385"        # material.fk_user (idPersona de CIMA)
DOCENTE = "Rodas Rosales Oscar Alexis"
OTHER_TEACHER = "99999"


def add_oracion(owner_id=TEACHER, *, title="Oraciones de práctica", nombre=DOCENTE):
    material = Material(
        nombre_material=title,
        tipo_material=TIPO_ORACION,
        path_preguntas="La luna brilla.\nEl río canta.",
        path_texto=None,
        path_texto_resumen=None,
        path_audio=None,
        path_audio_resumen=None,
        fk_user=owner_id,
        fk_user_name=nombre,
    )
    db.session.add(material)
    db.session.commit()
    return material.id


def make_cuento_on_disk(app, tmp_path, *, owner_id=TEACHER, nombre=DOCENTE, title="El bosque que escucha"):
    material_dir = tmp_path / "material"
    material_dir.mkdir(exist_ok=True)
    (material_dir / "texto.txt").write_text("Texto completo del cuento.", encoding="utf-8")
    (material_dir / "resumen.txt").write_text("Resumen del cuento.", encoding="utf-8")
    (material_dir / "audio.wav").write_bytes(b"RIFFfake-full-wav")
    (material_dir / "audio_resumen.wav").write_bytes(b"RIFFfake-summary-wav")
    questions = [{"pregunta": "¿Quién es el personaje?", "respuesta_esperada": "Luna"}]
    (material_dir / "preguntas.json").write_text(
        json.dumps(questions, ensure_ascii=False), encoding="utf-8"
    )
    with app.app_context():
        material = Material(
            nombre_material=title,
            tipo_material=TIPO_CUENTO,
            path_texto="material/texto.txt",
            path_texto_resumen="material/resumen.txt",
            path_audio="material/audio.wav",
            path_audio_resumen="material/audio_resumen.wav",
            path_preguntas="material/preguntas.json",
            fk_user=owner_id,
            fk_user_name=nombre,
        )
        db.session.add(material)
        db.session.commit()
        return material.id


@pytest.fixture()
def static_tmp(app, tmp_path, monkeypatch):
    # Los archivos de materiales viven bajo UPLOADS_ROOT (fuera de static/).
    monkeypatch.setitem(app.config, "UPLOADS_ROOT", str(tmp_path))
    return tmp_path


def test_list_materials_by_teacher_id_exposes_the_teacher_name(app, client, static_tmp):
    make_cuento_on_disk(app, static_tmp)

    # `dni` sigue aceptándose como alias histórico de `teacher_id`.
    for param in ("teacher_id", "dni"):
        response = client.get(f"/api/materials?{param}={TEACHER}")
        assert response.status_code == 200
        body = response.get_json()
        assert [m["docente"] for m in body] == [DOCENTE]
        assert "dni" not in body[0]

    assert client.get(f"/api/materials?teacher_id={OTHER_TEACHER}").get_json() == []


def test_list_materials_by_docente_name(app, client, static_tmp):
    make_cuento_on_disk(app, static_tmp)

    exact = client.get(f"/api/materials?docente={DOCENTE}")
    assert exact.status_code == 200
    assert [m["docente"] for m in exact.get_json()] == [DOCENTE]

    # Sin distinguir mayúsculas (el robot puede mandar el nombre en crudo de CIMA).
    loose = client.get(f"/api/materials?docente={DOCENTE.upper()}")
    assert [m["id"] for m in loose.get_json()] == [m["id"] for m in exact.get_json()]

    assert client.get("/api/materials?docente=Otra Docente Cualquiera").get_json() == []


def test_download_and_get_accept_the_docente_name(app, client, static_tmp):
    material_id = make_cuento_on_disk(app, static_tmp)

    assert client.get(
        f"/api/materials/{material_id}?docente={DOCENTE}"
    ).status_code == 200
    assert client.get(
        f"/api/materials/{material_id}/audio?docente={DOCENTE.lower()}"
    ).status_code == 200
    assert client.get(
        f"/api/materials/{material_id}/audio?docente=Quien Sea"
    ).status_code == 403


def test_list_materials_requires_an_identifier(client):
    assert client.get("/api/materials").status_code == 400


def test_list_materials_filters_by_tipo(app, client, static_tmp):
    make_cuento_on_disk(app, static_tmp)
    with app.app_context():
        add_oracion()

    everything = client.get(f"/api/materials?teacher_id={TEACHER}")
    assert {m["tipo_material"] for m in everything.get_json()} == {"cuento", "oracion"}

    only_cuentos = client.get(f"/api/materials?teacher_id={TEACHER}&tipo=cuento")
    body = only_cuentos.get_json()
    assert len(body) == 1 and body[0]["tipo_material"] == "cuento"

    assert [m["tipo_material"] for m in client.get(
        f"/api/materials?teacher_id={TEACHER}&tipo=oracion"
    ).get_json()] == ["oracion"]


def test_list_materials_rejects_an_unknown_tipo(client):
    assert client.get(f"/api/materials?teacher_id={TEACHER}&tipo=poema").status_code == 400


def test_get_material_scopes_by_teacher_id_when_given(app, client, static_tmp):
    material_id = make_cuento_on_disk(app, static_tmp)

    assert client.get(f"/api/materials/{material_id}?teacher_id={TEACHER}").status_code == 200
    assert client.get(
        f"/api/materials/{material_id}?teacher_id={OTHER_TEACHER}"
    ).status_code == 403
    # Sin identificador sigue funcionando por compatibilidad.
    assert client.get(f"/api/materials/{material_id}").status_code == 200


@pytest.mark.parametrize(
    "recurso, content_type, body_check",
    [
        ("texto", "text/plain", b"Texto completo del cuento."),
        ("resumen", "text/plain", b"Resumen del cuento."),
        ("audio", "audio/wav", b"RIFFfake-full-wav"),
        ("audio-resumen", "audio/wav", b"RIFFfake-summary-wav"),
        ("preguntas", "application/json", b'"respuesta_esperada"'),
    ],
)
def test_download_each_cuento_resource(
    app, client, static_tmp, recurso, content_type, body_check
):
    material_id = make_cuento_on_disk(app, static_tmp)
    response = client.get(f"/api/materials/{material_id}/{recurso}?teacher_id={TEACHER}")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith(content_type)
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert body_check in response.data


def test_download_requires_an_identifier(app, client, static_tmp):
    material_id = make_cuento_on_disk(app, static_tmp)
    assert client.get(f"/api/materials/{material_id}/audio").status_code == 400


def test_download_rejects_a_foreign_teacher(app, client, static_tmp):
    material_id = make_cuento_on_disk(app, static_tmp)
    assert client.get(
        f"/api/materials/{material_id}/audio?teacher_id={OTHER_TEACHER}"
    ).status_code == 403


def test_download_unknown_resource_is_404(app, client, static_tmp):
    material_id = make_cuento_on_disk(app, static_tmp)
    assert client.get(
        f"/api/materials/{material_id}/portada?teacher_id={TEACHER}"
    ).status_code == 404


def test_download_missing_file_on_disk_is_404(app, client, static_tmp):
    material_id = make_cuento_on_disk(app, static_tmp)
    (static_tmp / "material" / "audio.wav").unlink()
    assert client.get(
        f"/api/materials/{material_id}/audio?teacher_id={TEACHER}"
    ).status_code == 404


def test_oracion_exposes_only_oraciones(app, client):
    with app.app_context():
        material_id = add_oracion()

    oraciones = client.get(f"/api/materials/{material_id}/oraciones?teacher_id={TEACHER}")
    assert oraciones.status_code == 200
    assert oraciones.get_json() == {"oraciones": ["La luna brilla.", "El río canta."]}

    assert client.get(
        f"/api/materials/{material_id}/audio?teacher_id={TEACHER}"
    ).status_code == 404


def test_cuento_does_not_expose_oraciones(app, client, static_tmp):
    material_id = make_cuento_on_disk(app, static_tmp)
    assert client.get(
        f"/api/materials/{material_id}/oraciones?teacher_id={TEACHER}"
    ).status_code == 404


def test_save_material_stamps_the_logged_in_teacher_name(app, client, static_tmp):
    # La sesión de pruebas es TEST_TEACHER: id DOC-TEST-1, nombre formateado
    # "Docente de pruebas" para la UI, pero `fk_user_name` debe guardar la
    # forma cruda que envía la API institucional ("raw_name"), no la
    # formateada.
    save = client.post(
        "/api/material/save",
        data={
            "tipo_material": "oracion",
            "title": "Oraciones nuevas",
            "sentences_json": json.dumps(["Hoy llueve.", "Mañana saldrá el sol."]),
        },
    )
    assert save.status_code == 200
    material_id = save.get_json()["material_id"]

    body = client.get(f"/api/materials/{material_id}?teacher_id=DOC-TEST-1").get_json()
    assert body["docente"] == "DOCENTE DE PRUEBAS"

    with app.app_context():
        assert db.session.get(Material, material_id).fk_user_name == "DOCENTE DE PRUEBAS"
