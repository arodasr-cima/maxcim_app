from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from maxcim import create_app
from maxcim.extensions import db
from maxcim.models import CimaLearningSession, CimaSession, LearningSession, User
from maxcim.services.cima_api import (
    AuthenticatedTeacher,
    CimaAuthenticationError,
    CimaUnavailableError,
    Classroom,
    Student,
)


class FakeCimaClient:
    def __init__(self):
        self.student_calls = 0
        self.last_login_kind = None

    def _teacher(self):
        return AuthenticatedTeacher(
            teacher_id="DOC-314",
            authorization="Bearer upstream-secret-token",
            display_name="Docente Oficial",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def authenticate_email(self, email, password, identifier):
        assert email == "docente@cima.edu.pe"
        assert password == "clave-oficial"
        assert identifier
        self.last_login_kind = "email"
        return self._teacher()

    def authenticate_username(self, username, password, identifier):
        assert username == "bcesar"
        assert password == "clave-oficial"
        assert identifier
        self.last_login_kind = "username"
        return self._teacher()

    def list_classrooms(self, authorization, teacher_id):
        assert authorization == "Bearer upstream-secret-token"
        assert teacher_id == "DOC-314"
        return [Classroom("2165", "N", "5TH - A SEC. A.U. MAÑANA", True)]

    def list_students(self, authorization, classroom_id, classroom_type, order):
        assert authorization == "Bearer upstream-secret-token"
        assert (classroom_id, classroom_type, order) == ("2165", "N", "A")
        self.student_calls += 1
        return [Student("53362", "Adriano", "Amaya Gomes")]


@pytest.fixture()
def official_app(tmp_path):
    fake = FakeCimaClient()
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "official-test-secret",
            "AUTH_PROVIDER": "cima",
            "CIMA_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "CIMA_API_CLIENT": fake,
            "CIMA_API_IDENTIFIER": "test-browser",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'official.db'}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "DEMO_MODE": False,
            "SEED_DEMO_DATA": False,
            "AUTO_CREATE_DB": True,
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
        }
    )
    application.fake_cima = fake
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def official_client(official_app):
    return official_app.test_client()


def login(official_client, identity="docente@cima.edu.pe"):
    return official_client.post(
        "/login",
        data={"identity": identity, "password": "clave-oficial"},
        follow_redirects=False,
    )


def test_official_login_stores_only_encrypted_token_server_side(official_client, official_app):
    response = login(official_client)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert "upstream-secret-token" not in response.headers["Set-Cookie"]
    with official_client.session_transaction() as browser_session:
        assert "cima_session_id" in browser_session
        assert all("upstream-secret-token" not in str(value) for value in browser_session.values())
    with official_app.app_context():
        record = CimaSession.query.one()
        plaintext = Fernet(official_app.config["CIMA_TOKEN_ENCRYPTION_KEY"].encode()).decrypt(
            record.token_ciphertext.encode()
        )
        assert "upstream-secret-token" not in record.token_ciphertext
        assert plaintext == b"Bearer upstream-secret-token"
        assert record.identity.teacher_id == "DOC-314"
        assert "clave-oficial" not in User.query.one().password_hash


def test_official_dashboard_and_students_use_live_contract(official_client, official_app):
    login(official_client)

    dashboard = official_client.get("/dashboard")
    classroom = official_client.get("/aulas/2165?type=N&order=A")

    dashboard_html = dashboard.get_data(as_text=True)
    classroom_html = classroom.get_data(as_text=True)
    assert dashboard.status_code == 200
    assert "5TH - A SEC. A.U. MAÑANA" in dashboard_html
    assert "Promedio 82%" not in dashboard_html
    assert classroom.status_code == 200
    assert classroom.headers["Cache-Control"] == "no-store"
    assert "Adriano Amaya Gomes" in classroom_html
    assert "DNI" in classroom_html
    assert "73566673" not in classroom_html
    assert "drive.google.com" not in classroom_html
    assert "menor@cima.edu.pe" not in classroom_html
    assert official_app.fake_cima.student_calls == 1
    assert official_client.get("/health").get_json() == {"status": "ok", "mode": "cima"}


def test_classroom_membership_is_checked_before_students(official_client, official_app):
    login(official_client)

    response = official_client.get("/aulas/9999?type=N")

    assert response.status_code == 404
    assert official_app.fake_cima.student_calls == 0

    wrong_type = official_client.get("/aulas/2165?type=G")
    assert wrong_type.status_code == 404
    assert official_app.fake_cima.student_calls == 0


def test_username_login_and_logout_remove_server_session(official_client, official_app):
    assert login(official_client, "bcesar").status_code == 302
    assert official_app.fake_cima.last_login_kind == "username"

    response = official_client.post("/logout")

    assert response.status_code == 302
    with official_app.app_context():
        assert CimaSession.query.count() == 0


def test_expired_server_session_forces_a_new_login(official_client, official_app):
    login(official_client)
    with official_app.app_context():
        record = CimaSession.query.one()
        record.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()

    response = official_client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with official_app.app_context():
        assert CimaSession.query.count() == 0


def test_upstream_unauthorized_revokes_local_session(official_client, official_app):
    login(official_client)

    def rejected(_authorization, _teacher_id):
        raise CimaAuthenticationError()

    official_app.fake_cima.list_classrooms = rejected
    response = official_client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with official_app.app_context():
        assert CimaSession.query.count() == 0


def test_temporary_upstream_failure_never_falls_back_to_demo_data(official_client, official_app):
    login(official_client)

    def unavailable(_authorization, _teacher_id):
        raise CimaUnavailableError()

    official_app.fake_cima.list_classrooms = unavailable
    response = official_client.get("/dashboard")
    html = response.get_data(as_text=True)

    assert response.status_code == 503
    assert "No se pudieron actualizar las aulas" in html
    assert "3.º A — Secundaria" not in html
    assert 'class="stat-card"' not in html
    with official_app.app_context():
        assert CimaSession.query.count() == 1


def test_planned_session_keeps_official_classroom_identity(official_client, official_app):
    login(official_client)

    response = official_client.post(
        "/sesiones/nueva",
        data={
            "title": "Escucha oficial",
            "classroom": "2165:N",
            "scheduled_at": "2026-09-01T10:30",
        },
    )

    assert response.status_code == 302
    with official_app.app_context():
        learning_session = LearningSession.query.filter_by(title="Escucha oficial").one()
        link = CimaLearningSession.query.filter_by(learning_session_id=learning_session.id).one()
        assert learning_session.classroom == "5TH - A SEC. A.U. MAÑANA"
        assert (link.classroom_id, link.classroom_type) == ("2165", "N")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"CIMA_TOKEN_ENCRYPTION_KEY": "invalid"}, "Fernet"),
        ({"CIMA_API_TIMEOUT_SECONDS": 0}, "TIMEOUT"),
        ({"CIMA_API_SESSION_MAX_AGE_SECONDS": 60}, "SESSION_MAX_AGE"),
    ],
)
def test_official_mode_fails_fast_on_unsafe_configuration(tmp_path, override, message):
    config = {
        "TESTING": True,
        "SECRET_KEY": "safe-test-secret",
        "AUTH_PROVIDER": "cima",
        "CIMA_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'invalid.db'}",
        "UPLOAD_FOLDER": str(tmp_path / "uploads-invalid"),
        "AUTO_CREATE_DB": False,
    }
    config.update(override)

    with pytest.raises(RuntimeError, match=message):
        create_app(config)


def test_official_mode_requires_secure_cookie_outside_local_tests(tmp_path):
    with pytest.raises(RuntimeError, match="SESSION_COOKIE_SECURE"):
        create_app(
            {
                "TESTING": False,
                "SECRET_KEY": "persistent-secret-with-at-least-32-characters",
                "SECRET_KEY_EPHEMERAL": False,
                "AUTH_PROVIDER": "cima",
                "CIMA_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                "SESSION_COOKIE_SECURE": False,
                "CIMA_ALLOW_INSECURE_LOCAL_COOKIES": False,
                "CIMA_API_TEACHER_ID_CLAIM": "idUsuario",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'secure.db'}",
                "UPLOAD_FOLDER": str(tmp_path / "secure-uploads"),
                "AUTO_CREATE_DB": False,
            }
        )


def test_official_mode_requires_confirmed_teacher_claim(tmp_path):
    with pytest.raises(RuntimeError, match="TEACHER_ID_CLAIM"):
        create_app(
            {
                "TESTING": False,
                "SECRET_KEY": "persistent-secret-with-at-least-32-characters",
                "AUTH_PROVIDER": "cima",
                "CIMA_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                "SESSION_COOKIE_SECURE": True,
                "CIMA_API_TEACHER_ID_CLAIM": "",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'claim.db'}",
                "UPLOAD_FOLDER": str(tmp_path / "claim-uploads"),
                "AUTO_CREATE_DB": False,
            }
        )
