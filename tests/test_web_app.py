def test_teacher_pages_and_pwa_assets_render(client):
    for path in ("/dashboard", "/material", "/sesiones"):
        response = client.get(path)
        assert response.status_code == 200
        assert b"MAXCIM" in response.data

    manifest = client.get("/static/manifest.webmanifest")
    assert manifest.status_code == 200
    assert manifest.get_json()["short_name"] == "MAXCIM"

    service_worker = client.get("/service-worker.js")
    assert service_worker.status_code == 200
    assert service_worker.headers["Service-Worker-Allowed"] == "/"
    assert service_worker.headers["Cache-Control"] == "no-cache"

    material_page = client.get("/material")
    assert b'id="storyDuration"' in material_page.data
    assert b'min="1" max="15"' in material_page.data

    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json() == {"status": "ok"}


def test_story_validation_runs_before_gemini(client):
    missing_fields = client.post("/api/story/generate", json={"character": "Luna"})
    assert missing_fields.status_code == 400
    assert "lugar de la historia" in missing_fields.get_json()["error"]

    configured_story = client.post("/api/story/generate", json={
        "character": "Luna",
        "setting": "el bosque",
        "grade_level": "tercero de primaria",
        "objective": "escucha activa",
        "duration_minutes": 5,
    })
    assert configured_story.status_code == 503
    assert "GOOGLE_API_KEY" in configured_story.get_json()["error"]


def test_story_and_tts_duration_validation_run_before_gemini(client):
    invalid_story = client.post("/api/story/generate", json={
        "character": "Luna",
        "setting": "el bosque",
        "grade_level": "tercero de primaria",
        "objective": "escucha activa",
        "duration_minutes": 16,
    })
    assert invalid_story.status_code == 400
    assert "entre 1 y 15 minutos" in invalid_story.get_json()["error"]

    invalid_tts = client.post("/api/material/tts", json={
        "text": "Un cuento breve.",
        "target_duration_minutes": 0,
    })
    assert invalid_tts.status_code == 400
    assert "entre 1 y 15 minutos" in invalid_tts.get_json()["error"]
