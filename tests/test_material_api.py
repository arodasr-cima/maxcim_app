from __future__ import annotations

import io
import json
import wave
from pathlib import Path

from maxcim.extensions import db
from maxcim.models import Material, User
from maxcim.services.ai import demo_wav


def test_api_requires_authentication(client):
    assert client.get("/api/materials").status_code == 401
    assert client.post("/api/material/questions", json={}).status_code == 401


def test_process_txt_in_demo_mode(logged_client):
    response = logged_client.post(
        "/api/material/process",
        data={"file": (io.BytesIO(b"Una historia breve para escuchar."), "historia.txt")},
        content_type="multipart/form-data",
    )
    data = response.get_json()
    assert response.status_code == 200
    assert data["demo_mode"] is True
    assert "historia breve" in data["transcribed_text"]
    assert data["summary_text"]


def test_process_rejects_unknown_extension(logged_client):
    response = logged_client.post(
        "/api/material/process",
        data={"file": (io.BytesIO(b"binary"), "archivo.exe")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 415


def test_generate_exact_question_counts(logged_client):
    response = logged_client.post(
        "/api/material/questions",
        json={
            "text": "Luna escuchó con atención y luego respondió.",
            "counts": {"literales": 3, "inferenciales": 2, "criticas": 1},
        },
    )
    data = response.get_json()
    assert response.status_code == 200
    assert {key: len(value) for key, value in data["questions"].items()} == {
        "literales": 3,
        "inferenciales": 2,
        "criticas": 1,
    }


def test_tts_returns_valid_wav(logged_client):
    response = logged_client.post("/api/material/tts", json={"text": "Texto para narrar."})
    assert response.status_code == 200
    assert response.mimetype == "audio/wav"
    assert response.data.startswith(b"RIFF")
    with wave.open(io.BytesIO(response.data), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getnframes() > 0


def _material_payload(title="Lectura creada"):
    questions = [{"tipo": "literal", "pregunta": "¿Qué ocurrió?"}]
    return {
        "title": title,
        "skill": "Comunicación oral",
        "transcribed_text": "Texto completo de demostración.",
        "summary_text": "Resumen demostrativo.",
        "questions_json": json.dumps(questions),
        "audio_full": (io.BytesIO(demo_wav("Texto completo")), "audio.wav"),
        "audio_summary": (io.BytesIO(demo_wav("Resumen")), "resumen.wav"),
    }


def test_save_download_and_delete_material(logged_client, app):
    saved = logged_client.post(
        "/api/material/save",
        data=_material_payload(),
        content_type="multipart/form-data",
    )
    assert saved.status_code == 201
    material_id = saved.get_json()["material"]["id"]

    detail = logged_client.get(f"/api/materials/{material_id}")
    assert detail.status_code == 200
    assert detail.get_json()["titulo"] == "Lectura creada"

    downloaded = logged_client.get(f"/media/materials/{material_id}/texto")
    assert downloaded.status_code == 200
    assert b"Texto completo" in downloaded.data

    with app.app_context():
        directory = db.session.get(Material, material_id).storage_directory
        storage_path = app.config["UPLOAD_FOLDER"]

    deleted = logged_client.delete(f"/api/materials/{material_id}")
    assert deleted.status_code == 204
    with app.app_context():
        assert db.session.get(Material, material_id) is None
    assert not (Path(storage_path) / directory).exists()


def test_user_cannot_read_another_users_material(logged_client, app):
    with app.app_context():
        material_id = Material.query.first().id
        other = User(email="otra@maxcim.demo", display_name="Otra Docente", initials="OD")
        other.set_password("OtraClave2026!")
        db.session.add(other)
        db.session.commit()

    logged_client.post("/logout")
    logged_client.post("/login", data={"email": "otra@maxcim.demo", "password": "OtraClave2026!"})
    assert logged_client.get(f"/api/materials/{material_id}").status_code == 404
    assert logged_client.get(f"/media/materials/{material_id}/texto").status_code == 404
