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


def test_story_validation_runs_before_gemini(client):
    missing_fields = client.post("/api/story/generate", json={"character": "Luna"})
    assert missing_fields.status_code == 400
    assert "lugar de la historia" in missing_fields.get_json()["error"]

    configured_story = client.post("/api/story/generate", json={
        "character": "Luna",
        "setting": "el bosque",
        "grade_level": "tercero de primaria",
        "objective": "escucha activa",
    })
    assert configured_story.status_code == 503
    assert "GOOGLE_API_KEY" in configured_story.get_json()["error"]
