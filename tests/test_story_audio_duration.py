import json
from types import SimpleNamespace

import app as app_module


class StoryModels:
    def __init__(self):
        self.prompts = []

    def generate_content(self, *, contents, **_kwargs):
        self.prompts.append(contents)
        if len(self.prompts) == 1:
            story = "Luna escuchó y ayudó felizmente."
        else:
            story = " ".join(["palabra"] * 125)
        return SimpleNamespace(text=json.dumps({
            "titulo": "Luna y el bosque",
            "cuento": story,
            "resumen": "Luna aprendió a escuchar.",
        }))


class SpeechModels:
    def __init__(self):
        self.prompts = []

    def generate_content(self, *, contents, **_kwargs):
        self.prompts.append(contents)
        pcm_two_seconds = b"\0" * (24_000 * 2 * 2)
        inline_data = SimpleNamespace(
            data=pcm_two_seconds,
            mime_type="audio/pcm;rate=24000",
        )
        part = SimpleNamespace(inline_data=inline_data)
        content = SimpleNamespace(parts=[part])
        return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


def test_story_is_corrected_toward_selected_duration(client, monkeypatch):
    models = StoryModels()
    monkeypatch.setattr(
        app_module,
        "gemini_client",
        SimpleNamespace(models=models),
    )

    response = client.post("/api/story/generate", json={
        "character": "Luna",
        "setting": "el bosque",
        "grade_level": "tercero de primaria",
        "objective": "escucha activa",
        "duration_minutes": 1,
    })

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["target_duration_minutes"] == 1
    assert payload["word_count"] == 125
    assert payload["estimated_duration_seconds"] == 60
    assert len(models.prompts) == 2


def test_tts_reports_measured_wav_duration(client, monkeypatch):
    models = SpeechModels()
    monkeypatch.setattr(
        app_module,
        "gemini_client",
        SimpleNamespace(models=models),
    )
    story = " ".join(["palabra"] * 125)

    response = client.post("/api/material/tts", json={
        "text": story,
        "target_duration_minutes": 1,
    })

    assert response.status_code == 200
    assert response.mimetype == "audio/wav"
    assert response.headers["X-MAXCIM-Audio-Duration-Seconds"] == "2.00"
    assert response.headers["X-MAXCIM-Target-Duration-Minutes"] == "1"
    assert "125 palabras por minuto" in models.prompts[0]
