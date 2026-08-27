from __future__ import annotations

import re

from maxcim import create_app
from maxcim.extensions import db
from maxcim.models import LearningSession


def test_health_and_login_are_public(client):
    assert client.get("/health").get_json() == {"status": "ok", "mode": "demo"}
    page = client.get("/login")
    assert page.status_code == 200
    assert b"docente@maxcim.demo" in page.data


def test_private_pages_redirect_to_login(client):
    for path in ("/dashboard", "/material", "/sesiones"):
        response = client.get(path)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


def test_invalid_and_valid_login(client, app):
    invalid = client.post("/login", data={"email": app.config["DEMO_EMAIL"], "password": "incorrecta"})
    assert invalid.status_code == 200
    assert "Correo o contraseña incorrectos" in invalid.get_data(as_text=True)

    valid = client.post(
        "/login",
        data={"email": app.config["DEMO_EMAIL"], "password": app.config["DEMO_PASSWORD"]},
    )
    assert valid.status_code == 302
    assert valid.headers["Location"].endswith("/dashboard")
    cookie = valid.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_login_blocks_external_redirect(client, app):
    response = client.post(
        "/login?next=https://example.test/phishing",
        data={"email": app.config["DEMO_EMAIL"], "password": app.config["DEMO_PASSWORD"]},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_csrf_is_enforced_and_valid_token_is_accepted(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "csrf-test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'csrf.db'}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "DEMO_MODE": True,
            "SEED_DEMO_DATA": True,
            "WTF_CSRF_ENABLED": True,
            "RATELIMIT_ENABLED": False,
        }
    )
    csrf_client = application.test_client()
    rejected = csrf_client.post(
        "/login",
        data={"email": application.config["DEMO_EMAIL"], "password": application.config["DEMO_PASSWORD"]},
    )
    assert rejected.status_code == 400

    login_page = csrf_client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', login_page).group(1)
    accepted = csrf_client.post(
        "/login",
        data={
            "email": application.config["DEMO_EMAIL"],
            "password": application.config["DEMO_PASSWORD"],
            "csrf_token": token,
        },
    )
    assert accepted.status_code == 302

    protected_api = csrf_client.post(
        "/api/material/questions",
        json={
            "text": "Luna escucha y responde con respeto.",
            "counts": {"literales": 1, "inferenciales": 0, "criticas": 0},
        },
        headers={"X-CSRFToken": token},
    )
    assert protected_api.status_code == 200

    with application.app_context():
        db.session.remove()
        db.drop_all()


def test_dashboard_and_material_render(logged_client):
    dashboard = logged_client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Panel docente" in dashboard.get_data(as_text=True)
    assert "Docente Demo" in dashboard.get_data(as_text=True)

    material = logged_client.get("/material")
    html = material.get_data(as_text=True)
    assert material.status_code == 200
    assert "El poder de escuchar" in html
    assert 'data-skill="Escucha activa"' in html


def test_create_and_complete_session(logged_client, app):
    created = logged_client.post(
        "/sesiones/nueva",
        data={
            "title": "Diálogo respetuoso",
            "classroom": "3.º A — Secundaria",
            "scheduled_at": "2026-09-01T10:30",
        },
    )
    assert created.status_code == 302

    with app.app_context():
        item = LearningSession.query.filter_by(title="Diálogo respetuoso").one()
        session_id = item.id
        assert item.status == "programada"

    toggled = logged_client.post(f"/sesiones/{session_id}/estado")
    assert toggled.status_code == 302
    with app.app_context():
        assert db.session.get(LearningSession, session_id).status == "completada"


def test_security_headers_are_present(logged_client):
    response = logged_client.get("/dashboard")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
